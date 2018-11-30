from systest import TestCase


class AssertsEqualTest(TestCase):

    def __init__(self, first, second):
        super(AssertsEqualTest, self).__init__()
        self.first = first
        self.second = second

    def run(self):
        self.assert_equal(self.first, self.second)


class AssertsNotEqualTest(TestCase):

    def __init__(self, first, second):
        super(AssertsNotEqualTest, self).__init__()
        self.first = first
        self.second = second

    def run(self):
        self.assert_not_equal(self.first, self.second)


class AssertsTrueTest(TestCase):

    def __init__(self, condition):
        super(AssertsTrueTest, self).__init__()
        self.condition = condition

    def run(self):
        self.assert_true(self.condition)


class AssertsFalseTest(TestCase):

    def __init__(self, condition):
        super(AssertsFalseTest, self).__init__()
        self.condition = condition

    def run(self):
        self.assert_false(self.condition)


class AssertsInTest(TestCase):

    def __init__(self, member, container):
        super(AssertsInTest, self).__init__()
        self.member = member
        self.container = container

    def run(self):
        self.assert_in(self.member, self.container)


class AssertsNotInTest(TestCase):

    def __init__(self, member, container):
        super(AssertsNotInTest, self).__init__()
        self.member = member
        self.container = container

    def run(self):
        self.assert_not_in(self.member, self.container)


class AssertsIsNoneTest(TestCase):

    def __init__(self, obj):
        super(AssertsIsNoneTest, self).__init__()
        self.obj = obj

    def run(self):
        self.assert_is_none(self.obj)


class AssertsIsNotNoneTest(TestCase):

    def __init__(self, obj):
        super(AssertsIsNotNoneTest, self).__init__()
        self.obj = obj

    def run(self):
        self.assert_is_not_none(self.obj)


class AssertsGreaterTest(TestCase):

    def __init__(self, first, second):
        super(AssertsGreaterTest, self).__init__()
        self.first = first
        self.second = second

    def run(self):
        self.assert_greater(self.first, self.second)


class AssertsGreaterEqualTest(TestCase):

    def __init__(self, first, second):
        super(AssertsGreaterEqualTest, self).__init__()
        self.first = first
        self.second = second

    def run(self):
        self.assert_greater_equal(self.first, self.second)


class AssertsLessTest(TestCase):

    def __init__(self, first, second):
        super(AssertsLessTest, self).__init__()
        self.first = first
        self.second = second

    def run(self):
        self.assert_less(self.first, self.second)


class AssertsLessEqualTest(TestCase):

    def __init__(self, first, second):
        super(AssertsLessEqualTest, self).__init__()
        self.first = first
        self.second = second

    def run(self):
        self.assert_less_equal(self.first, self.second)


class AssertsRaisesNoExceptionTest(TestCase):

    def run(self):
        with self.assert_raises(ValueError):
            pass


class AssertsRaisesWrongExceptionTest(TestCase):

    def run(self):
        with self.assert_raises(ValueError):
            raise TypeError('This is not a value error.')


class AssertsNoneTest(TestCase):

    def __init__(self, obj):
        super(AssertsNoneTest, self).__init__()
        self.obj = obj

    def run(self):
        self.assert_none(self.obj)
