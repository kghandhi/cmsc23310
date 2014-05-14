import unittest 

import simulate

class TestSimulateStaticFunctions(unittest.TestCase):
    TEST_BASE_PATH = "./tests/{}"
    SIMPLE_TEST = TEST_BASE_PATH.format("paxos.simple-clean.in")
    UNCLEAN_TEST = TEST_BASE_PATH.format("paxos.simple.in")

    def _test_proc_input_simple(self, path):
        with open(path) as f:
            n_p, n_a, t_max, E = simulate.proc_input(f)

            empty_el = {'P': [], 'A': []}

            self.assertEqual(n_p, 1)
            self.assertEqual(n_a, 3)
            self.assertEqual(t_max, 15),
            self.assertDictEqual(E, {
                0: simulate.Event(0, empty_el, empty_el, [1], [42])
                })

    def test_proc_input_simple(self):
        for path in [self.SIMPLE_TEST, self.UNCLEAN_TEST]:
            self._test_proc_input_simple(path)



if __name__ == '__main__':
    unittest.main()
