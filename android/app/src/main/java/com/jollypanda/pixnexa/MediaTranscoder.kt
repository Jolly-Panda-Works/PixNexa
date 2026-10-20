package com.jollypanda.pixnexa

import android.content.Context
import android.media.MediaMetadataRetriever
import android.net.Uri
import androidx.annotation.OptIn
import androidx.media3.common.Effect
import androidx.media3.common.Format
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.UnstableApi
import androidx.media3.effect.Presentation
import androidx.media3.transformer.Codec
import androidx.media3.transformer.Composition
import androidx.media3.transformer.DefaultEncoderFactory
import androidx.media3.transformer.EditedMediaItem
import androidx.media3.transformer.Effects
import androidx.media3.transformer.EncoderUtil
import androidx.media3.transformer.ExportException
import androidx.media3.transformer.ExportResult
import androidx.media3.transformer.ProgressHolder
import androidx.media3.transformer.Transformer
import androidx.media3.transformer.VideoEncoderSettings
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.io.File
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * Video and audio work with Media3 Transformer, which uses the phone's own hardware encoders
 * (MediaCodec), so it is fast and needs no native code. Output is always an MP4 container:
 * H.264 or HEVC video with AAC audio, or AAC audio alone (.m4a).
 */
@OptIn(UnstableApi::class)
object MediaTranscoder {

    /** Video MIME types for [Request.videoMimeType] (the same strings as Media3's MimeTypes). */
    const val H264 = "video/avc"
    const val HEVC = "video/hevc"

    /** What to make from one video or audio file. */
    data class Request(
        /** [H264] or [HEVC]; null drops the video and keeps only the audio. */
        val videoMimeType: String?,
        /** Short side of the output in pixels; 0 keeps the resolution. Videos are never made larger. */
        val shortSide: Int = 0,
        /** Video bitrate as bits per pixel per frame; 0 lets the encoder choose. Forces a re-encode. */
        val bitsPerPixel: Float = 0f,
        /** AAC bitrate in bits per second; 0 keeps the audio as it is when the container allows it. */
        val audioBitrate: Int = 0,
    )

    /** True when this phone has an HEVC (H.265) encoder. Reads the codec list, so call it off the main thread. */
    fun hevcSupported(): Boolean = try {
        EncoderUtil.getSupportedMimeTypes().contains(HEVC)
    } catch (e: Exception) {
        false
    }

    /**
     * Exports [input] to [output] and suspends until it is done. [onProgress] gets 0..1.
     * Cancelling the coroutine stops the export. Transformer must live on a thread with a Looper,
     * so it is driven from the main thread; the heavy work runs on its own internal threads.
     */
    suspend fun transcode(
        context: Context,
        input: Uri,
        request: Request,
        output: File,
        onProgress: (Float) -> Unit,
    ) {
        val audioOnly = request.videoMimeType == null
        val info = if (audioOnly) null else withContext(Dispatchers.IO) { probe(context, input) }
        output.parentFile?.mkdirs()
        output.delete()

        withContext(Dispatchers.Main) {
            val app = context.applicationContext
            val videoEffects: List<Effect> = buildList {
                val size = info?.let { outputSize(it, request.shortSide) }
                if (size != null) add(Presentation.createForWidthAndHeight(size.first, size.second, Presentation.LAYOUT_SCALE_TO_FIT))
            }
            val videoBitrate = if (request.bitsPerPixel > 0f && info != null) {
                val (w, h) = outputSize(info, request.shortSide) ?: (info.width to info.height)
                (w.toFloat() * h * info.frameRate * request.bitsPerPixel).roundToInt().coerceIn(250_000, 40_000_000)
            } else {
                0
            }

            val defaultFactory = DefaultEncoderFactory.Builder(app)
                .apply {
                    if (videoBitrate > 0) {
                        setRequestedVideoEncoderSettings(VideoEncoderSettings.Builder().setBitrate(videoBitrate).build())
                    }
                }
                .setEnableFallback(true)
                .build()
            val encoderFactory = TunedEncoderFactory(
                delegate = defaultFactory,
                audioBitrate = request.audioBitrate,
                forceVideo = videoBitrate > 0,
                forceAudio = request.audioBitrate > 0,
            )

            val finished = CompletableDeferred<Unit>()
            val builder = Transformer.Builder(app)
                .setAudioMimeType(MimeTypes.AUDIO_AAC)
                .setEncoderFactory(encoderFactory)
                .addListener(object : Transformer.Listener {
                    override fun onCompleted(composition: Composition, exportResult: ExportResult) {
                        finished.complete(Unit)
                    }

                    override fun onError(composition: Composition, exportResult: ExportResult, exportException: ExportException) {
                        finished.completeExceptionally(ConvertException(errorMessage(exportException), exportException))
                    }
                })
            request.videoMimeType?.let { builder.setVideoMimeType(it) }
            val transformer = builder.build()

            val edited = EditedMediaItem.Builder(MediaItem.fromUri(input))
                .setRemoveVideo(audioOnly)
                .setEffects(Effects(emptyList(), videoEffects))
                .build()

            try {
                transformer.start(edited, output.absolutePath)
            } catch (e: IllegalArgumentException) {
                throw ConvertException(R.string.error_media, e)
            } catch (e: IllegalStateException) {
                throw ConvertException(R.string.error_media, e)
            }

            try {
                val holder = ProgressHolder()
                while (!finished.isCompleted) {
                    if (transformer.getProgress(holder) == Transformer.PROGRESS_STATE_AVAILABLE) {
                        onProgress(holder.progress / 100f)
                    }
                    delay(250)
                }
                finished.await()
            } finally {
                if (!finished.isCompleted) {
                    // Stopped by the user: cancel() also releases the codecs.
                    transformer.cancel()
                    output.delete()
                }
            }
        }
        if (!output.isFile || output.length() == 0L) {
            output.delete()
            throw ConvertException(R.string.error_media)
        }
    }

    private class VideoInfo(val width: Int, val height: Int, val frameRate: Float)

    /** Display size (rotation applied) and frame rate of a video, as far as the file tells. */
    private fun probe(context: Context, uri: Uri): VideoInfo? {
        val retriever = MediaMetadataRetriever()
        return try {
            retriever.setDataSource(context, uri)
            val w = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)?.toIntOrNull() ?: return null
            val h = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)?.toIntOrNull() ?: return null
            val rotation = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_ROTATION)?.toIntOrNull() ?: 0
            // METADATA_KEY_CAPTURE_FRAMERATE is only set for slow motion; 30 fps is a fair guess for bitrate maths.
            val fps = 30f
            if (rotation % 180 != 0) VideoInfo(h, w, fps) else VideoInfo(w, h, fps)
        } catch (e: Exception) {
            null
        } finally {
            try {
                retriever.release()
            } catch (ignored: Exception) {
            }
        }
    }

    /** Output size with the short side at [shortSide] (even numbers), or null when no scaling is needed. */
    private fun outputSize(info: VideoInfo, shortSide: Int): Pair<Int, Int>? {
        if (shortSide <= 0) return null
        val short = min(info.width, info.height)
        if (short <= shortSide) return null
        val scale = shortSide.toDouble() / short
        val w = max(2, (info.width * scale / 2).roundToInt() * 2)
        val h = max(2, (info.height * scale / 2).roundToInt() * 2)
        return w to h
    }

    private fun errorMessage(e: ExportException): Int = when (e.errorCode) {
        ExportException.ERROR_CODE_ENCODER_INIT_FAILED,
        ExportException.ERROR_CODE_ENCODING_FAILED,
        ExportException.ERROR_CODE_ENCODING_FORMAT_UNSUPPORTED -> R.string.error_encoder

        ExportException.ERROR_CODE_DECODER_INIT_FAILED,
        ExportException.ERROR_CODE_DECODING_FAILED,
        ExportException.ERROR_CODE_DECODING_FORMAT_UNSUPPORTED -> R.string.error_decoder

        ExportException.ERROR_CODE_IO_FILE_NOT_FOUND,
        ExportException.ERROR_CODE_IO_NO_PERMISSION,
        ExportException.ERROR_CODE_IO_UNSPECIFIED -> R.string.error_read

        else -> R.string.error_media
    }

    /**
     * The default encoders, plus a fixed AAC bitrate and a way to force re-encoding:
     * Transformer otherwise copies streams that are already H.264/AAC without touching them.
     */
    private class TunedEncoderFactory(
        private val delegate: DefaultEncoderFactory,
        private val audioBitrate: Int,
        private val forceVideo: Boolean,
        private val forceAudio: Boolean,
    ) : Codec.EncoderFactory {

        override fun createForAudioEncoding(format: Format): Codec {
            val tuned = if (audioBitrate > 0) {
                format.buildUpon().setAverageBitrate(audioBitrate).setPeakBitrate(audioBitrate).build()
            } else {
                format
            }
            return delegate.createForAudioEncoding(tuned)
        }

        override fun createForVideoEncoding(format: Format): Codec = delegate.createForVideoEncoding(format)

        override fun audioNeedsEncoding(): Boolean = forceAudio

        override fun videoNeedsEncoding(): Boolean = forceVideo
    }
}
