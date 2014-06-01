import json
import sys
import signal
import zmq
from zmq.eventloop import ioloop, zmqstream
ioloop.install()


class Group(object):
    def __init__(self, key_range, n_nodes, succ_g, pred_g, leader):
        self.key_range = key_range

        self.leader = leader
        self.group_table = dict() #routing table of the group
        self.n_nodes = n_nodes

        self.succ_g = succ_g #group that is the successor

        self.pred_g = pred_g #group that is the pred.


class Node(object):
    def __init__(self, node_name, pub_endpoint, router_endpoint, ...):
        self.name = node_name
        self.key = key_range #we might make all group members key distributions uniform

        self.pred = None #predecessor node
        self.succ = None #successor node

        self.store = dict()  #keys this node is responsible for (the primary)
        self.values = dict() #redundancy, additional coppies of keys, value pairs of group members

        self.group = None

        self.isLeader = False
        self.proposer = None #Proposer(name)
        self.acceptor = None #Proposer

        # SUB socket for receiving messages from the broker
        self.sub_sock = self.context.socket(zmq.SUB)
        self.sub_sock.connect(pub_endpoint)

        # make sure we get messages meant for us!
        self.sub_sock.set(zmq.SUBSCRIBE, node_name)
        self.sub = zmqstream.ZMQStream(self.sub_sock, self.loop)
        self.sub.on_recv(self.handle)
        
        # REQ socket for sending messages to the broker
        self.req_sock = self.context.socket(zmq.REQ)
        self.req_sock.connect(router_endpoint)
        self.req = zmqstream.ZMQStream(self.req_sock, self.loop)
        self.req.on_recv(self.handle_broker_message)

    ############
    ### IN PAXOS
    ############
    def handle_msg():
        pass

    def handle_set():
        pass

    def handle_merge():
        pass

    def handle_join():
        pass

    def handle_add_node():
        pass

    def handle_drop_node():
        pass

    ############
    ### QUICK
    ############

    def handle_ask():
        pass

    def handle_get_group_info():
        pass


