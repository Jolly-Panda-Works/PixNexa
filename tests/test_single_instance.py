import os
import time

from single_instance import SingleInstance


def test_second_instance_is_refused_and_can_send_paths(tmp_path):
    first, second = SingleInstance(tmp_path), SingleInstance(tmp_path)
    assert first.acquire() is True
    assert second.acquire() is False

    second.send([str(tmp_path / "a.png"), str(tmp_path / "عکس.jpg")])
    second.send([])                                    # launched again without a file: just "come to front"
    messages = first.collect()
    assert sorted(len(m) for m in messages) == [0, 2]
    assert first.collect() == []                       # each message is delivered once
    assert str(tmp_path / "عکس.jpg") in [p for m in messages for p in m]


def test_lock_is_free_again_after_release(tmp_path):
    first = SingleInstance(tmp_path)
    assert first.acquire()
    first.release()
    assert SingleInstance(tmp_path).acquire()


def test_stale_messages_are_dropped_by_a_new_instance(tmp_path):
    old = SingleInstance(tmp_path)
    old.send(["x.png"])
    msg = next(old.inbox.glob("*.msg"))
    past = time.time() - 3600
    os.utime(msg, (past, past))
    assert SingleInstance(tmp_path).acquire()
    assert not list(old.inbox.glob("*.msg"))


def test_broken_message_does_not_crash(tmp_path):
    first = SingleInstance(tmp_path)
    first.acquire()
    (first.inbox / "bad.msg").write_text("not json", encoding="utf-8")
    assert first.collect() == [[]]
