from systest import TestCase


class DescriptionNoneTest(TestCase):
    count = 0


class DescriptionEmptyTest(TestCase):
    ""


class DescriptionBlankTest(TestCase):
    """

    """


class DescriptionMultiLineTest(TestCase):
    """Line 1.
    Line 2.
    Line 3.

    """
