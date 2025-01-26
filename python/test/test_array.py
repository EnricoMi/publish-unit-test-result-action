import unittest


def next_offset(every, offset, len):
    return (offset - len % every) % every


class TestArray(unittest.TestCase):
    def test_next_offset_with_every_one(self):
        for len in range(10):
            with self.subTest(len=len):
                self.assertEqual(0, next_offset(1, 0, len))

    def test_next_offset_with_empty_list(self):
        for every in range(1, 6):
            for offset in range(every):
                with self.subTest(every=every, offset=offset):
                    self.assertEqual(offset, next_offset(every, offset, 0))

    def test_next_offset_short_list(self):
        for every in range(1, 6):
            for offset in range(every):
                for len in range(1, offset):
                    with self.subTest(every=every, offset=offset, len=len):
                        self.assertEqual(offset - len, next_offset(every, offset, len))

    def test_next_offset_multiple_len_list(self):
        for every in range(1, 6):
            for offset in range(every):
                for N in range(1, 5):
                    len = N * every
                    with self.subTest(every=every, offset=offset, len=len):
                        self.assertEqual(offset, next_offset(every, offset, len))

    def test_next_offset(self):
        self.assertEqual(1, next_offset(2, 0, 3))
        self.assertEqual(0, next_offset(2, 1, 3))

        self.assertEqual(0, next_offset(2, 0, 4))
        self.assertEqual(1, next_offset(2, 1, 4))

        self.assertEqual(2, next_offset(3, 0, 4))
        self.assertEqual(0, next_offset(3, 1, 4))
        self.assertEqual(1, next_offset(3, 2, 4))

        self.assertEqual(1, next_offset(3, 0, 5))
        self.assertEqual(2, next_offset(3, 1, 5))
        self.assertEqual(0, next_offset(3, 2, 5))

        self.assertEqual(0, next_offset(3, 0, 6))
        self.assertEqual(1, next_offset(3, 1, 6))
        self.assertEqual(2, next_offset(3, 2, 6))

        self.assertEqual(3, next_offset(4, 0, 5))
        self.assertEqual(0, next_offset(4, 1, 5))
        self.assertEqual(1, next_offset(4, 2, 5))
        self.assertEqual(2, next_offset(4, 3, 5))

        self.assertEqual(2, next_offset(4, 0, 6))
        self.assertEqual(3, next_offset(4, 1, 6))
        self.assertEqual(0, next_offset(4, 2, 6))
        self.assertEqual(1, next_offset(4, 3, 6))

        self.assertEqual(1, next_offset(4, 0, 7))
        self.assertEqual(2, next_offset(4, 1, 7))
        self.assertEqual(3, next_offset(4, 2, 7))
        self.assertEqual(0, next_offset(4, 3, 7))

        self.assertEqual(0, next_offset(4, 0, 8))
        self.assertEqual(1, next_offset(4, 1, 8))
        self.assertEqual(2, next_offset(4, 2, 8))
        self.assertEqual(3, next_offset(4, 3, 8))
