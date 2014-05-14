import unittest 

import simulate
import paxos

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

class TestAcceptor(unittest.TestCase):
    def _make_simple_message(self, msg_type): 
        return paxos.Message(0, msg_type, 1, 3, 0, []) 

    def setUp(self):
        self.messages = {
            key: self._make_simple_message(key) for key in
            ["PREPARE", "ACCEPT"]
        }
            

        self.acceptor = paxos.Acceptor(1)
        self.N = []

    def test_prepare_promise(self):
        self.acceptor.deliver_message(self.N, self.messages["PREPARE"])

        print "got: {}".format(self.N)

        self.assertEqual(len(self.N), 1)
        self.assertEqual(self.N[0], paxos.Message(0, "PROMISE", 3, 1, 0, []))

    def test_prepare_rejected(self):
        self.acceptor.n = 1

        self.acceptor.deliver_message(self.N, self.messages["PREPARE"])
        
        self.assertEqual(len(self.N), 1)
        self.assertEqual(self.N[0], self._make_simple_message("REJECTED"))

class TestProposer(unittest.TestCase):
    PROPOSE_MESSAGE = paxos.Message(0, "PROPOSE", [], [], 0, [])

    def setUp(self):
        self.proposer = paxos.Proposer(0, 
                                       [paxos.Acceptor(1),
                                        paxos.Acceptor(2)])
        self.N = []

    def test_propose_message(self):
        pass



if __name__ == '__main__':
    unittest.main()
