import systest


class CustomJsonSequencer(systest.Sequencer):

    def summary_json_test(self, test):
        summary = super(CustomJsonSequencer, self).summary_json_test(test)
        summary['data'] = test.data
        del summary['execution_time']

        return summary


class CustomJsonTest(systest.TestCase):

    def __init__(self, data):
        super(CustomJsonTest, self).__init__()
        self.data = data

    def run(self):
        pass
