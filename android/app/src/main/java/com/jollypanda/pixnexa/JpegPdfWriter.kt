package com.jollypanda.pixnexa

import java.io.BufferedOutputStream
import java.io.Closeable
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStream
import java.util.Locale

/**
 * Writes a PDF whose pages are JPEG images, stored as they are (DCTDecode).
 *
 * android.graphics.pdf.PdfDocument would store every bitmap losslessly (Flate), which makes the files
 * large and ignores the quality setting. Writing the few PDF objects by hand keeps the JPEG compression,
 * so the size follows the quality slider. Pages are streamed to disk one by one, so memory use stays low.
 */
class JpegPdfWriter(file: File) : Closeable {

    private val out = CountingStream(BufferedOutputStream(FileOutputStream(file), 64 * 1024))

    /** Byte offset of every object, by object number. Objects 1 (catalog) and 2 (pages) are written last. */
    private val offsets = HashMap<Int, Long>()
    private val pageObjects = ArrayList<Int>()
    private var nextObject = 3
    private var closed = false

    val pageCount: Int get() = pageObjects.size

    init {
        out.write("%PDF-1.4\n".toByteArray(Charsets.US_ASCII))
        // A comment with high bytes tells tools that the file is binary.
        out.write(byteArrayOf('%'.code.toByte(), 0xE2.toByte(), 0xE3.toByte(), 0xCF.toByte(), 0xD3.toByte(), '\n'.code.toByte()))
    }

    /**
     * Adds one page of [pageWidth] × [pageHeight] points (1/72 inch) and draws the JPEG [jpeg]
     * ([imageWidth] × [imageHeight] pixels, RGB) into the rectangle [x], [y], [width], [height] (points, origin bottom left).
     */
    fun addPage(
        jpeg: ByteArray,
        imageWidth: Int,
        imageHeight: Int,
        pageWidth: Float,
        pageHeight: Float,
        x: Float = 0f,
        y: Float = 0f,
        width: Float = pageWidth,
        height: Float = pageHeight,
    ) {
        val imageObj = nextObject++
        val contentObj = nextObject++
        val pageObj = nextObject++

        beginObject(imageObj)
        ascii(
            "<< /Type /XObject /Subtype /Image /Width $imageWidth /Height $imageHeight " +
                "/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpeg.size} >>\nstream\n"
        )
        out.write(jpeg)
        ascii("\nendstream\nendobj\n")

        val content = "q ${num(width)} 0 0 ${num(height)} ${num(x)} ${num(y)} cm /Im0 Do Q\n".toByteArray(Charsets.US_ASCII)
        beginObject(contentObj)
        ascii("<< /Length ${content.size} >>\nstream\n")
        out.write(content)
        ascii("\nendstream\nendobj\n")

        beginObject(pageObj)
        ascii(
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${num(pageWidth)} ${num(pageHeight)}] " +
                "/Resources << /XObject << /Im0 $imageObj 0 R >> >> /Contents $contentObj 0 R >>\nendobj\n"
        )
        pageObjects += pageObj
    }

    override fun close() {
        if (closed) return
        closed = true
        try {
            beginObject(2)
            ascii("<< /Type /Pages /Kids [${pageObjects.joinToString(" ") { "$it 0 R" }}] /Count ${pageObjects.size} >>\nendobj\n")
            beginObject(1)
            ascii("<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")

            val size = nextObject
            val xref = out.count
            val table = StringBuilder("xref\n0 $size\n0000000000 65535 f \n")
            for (n in 1 until size) {
                table.append(String.format(Locale.US, "%010d 00000 n \n", offsets[n] ?: 0L))
            }
            table.append("trailer\n<< /Size $size /Root 1 0 R >>\nstartxref\n$xref\n%%EOF\n")
            ascii(table.toString())
        } finally {
            out.close()
        }
    }

    private fun beginObject(number: Int) {
        offsets[number] = out.count
        ascii("$number 0 obj\n")
    }

    private fun ascii(text: String) = out.write(text.toByteArray(Charsets.US_ASCII))

    /** PDF numbers always use a dot and Latin digits, whatever the phone's language. */
    private fun num(value: Float): String = String.format(Locale.US, "%.2f", value)

    private class CountingStream(private val target: OutputStream) : OutputStream() {
        var count = 0L
            private set

        override fun write(b: Int) {
            target.write(b)
            count++
        }

        override fun write(b: ByteArray, off: Int, len: Int) {
            target.write(b, off, len)
            count += len
        }

        override fun flush() = target.flush()
        override fun close() = target.close()
    }

    companion object {
        /** A4 in points. */
        const val A4_WIDTH = 595.28f
        const val A4_HEIGHT = 841.89f
    }
}
