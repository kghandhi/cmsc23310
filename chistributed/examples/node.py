import json
import sys
import signal
import zmq
import time
import math
from __future__ import division
from datetime import datetime as dt
from datetime import timedelta
from zmq.eventloop import ioloop, zmqstream
ioloop.install()

MAX_GROUP = 10
MIN_GROUP = 4
#MAX_KEY = int('f'*128, 16)
MAX_KEY = 16


class Group(object):
  def __init__(self, key_range, leader, members):
    self.key_range = key_range
    self.leader = leader
    self.members = members
    self.p_num = 1
    

class Node(object):
  def __init__(self, node_name, pub_endpoint, router_endpoint, spammer, peer_names, pred_names, succ_names):
    self.loop = ioloop.ZMQIOLoop.instance()
    self.context = zmq.Context()

    self.connected = False

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

    self.name = node_name
    
    self.lgroup = None #group object
    self.rgroup = None #group object
    self.group = None #group object
    
    self.store = dict()
    
    self.leader = None
    self.leaderLease = dt.now()

    self.spammer = spammer
    self.peer_names = peer_names #eventually this will be our group
    self.okays = {} #dictionary of okays received hashed on "MERGE": (merge_type, source) or "SPLIT": int
  
    # Acceptor Attributes:
    self.n_int = dict() #highest prepare requests responded to hashed on the key
    self.acced = dict() #tuple values (value, n) hashed on key

    # Proposer Attributes:
    self.accs = [] #defined inside handle_paxos, redefined whenever we get a paxos message
    self.proposals = dict() #dictionary of proposals
    self.promises = dict() #lists of promises hashed on p_num
    self.rejects = dict() #(value, n) of rejected msgs hashed on n
    self.accepts = dict() #(value, n) of accepted msgs hashed on n
    self.props_accepted = dict() #concensus values indexed by n (proposed, accepted) tuples
    self.redirects = dict() #dictionary of dictionaries...

    for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
      signal.signal(sig, self.shutdown)


  def handle_split(self):
    old_key = self.group.key_range
    b = long(old_key[1])
    a = long(old_key[0])
    if (b < a):
      lrange = MAX_KEY - a
      half_range = (lrange + b) / 2
      if under < b:
        left_key = (a, b - half_range)
        right_key = (b - half_range, b)
      else:
        left_key = (a, a + half_range)
        right_key = (a + half_range, b)
    else:
      half_range = (b - a) / 2 
      left_key = (a, half_range + a)
      right_key = (half_range + a, b)

      old_ms = self.group.members
      l_sz = len(old_ms) / 2
      left_ms = [old_ms[i] for i in xrange(l_sz)]
      right_ms = [old_ms[i] for i in xrange(l_sz, len(old_ms))]
      new_left = Group(left_key, None, left_ms)
      new_right = Group(right_key, None, right_ms)

    return (new_left, new_right)

  def handle_merge(self, side):
    if side == "left":
      b = self.group.key_range[1]
      a = self.lgroup.key_range[0]
      new_ms = [x for x in self.group.members].extend(self.lgroup.members)
    
    elif side == "right":
      a = self.group.key_range[0]
      b = self.rgroup.key_range[1]
      new_ms = [x for x in self.group.members].extend(self.rgroup.members)
      
    new_group = Group((a,b), None, new_ms)
    #remember to paxos the self.store of each leader
    return new_group

  def start(self):
    '''
    Simple manual poller, dispatching received messages and sending those in
    the message queue whenever possible.
    '''
    self.loop.start()

    ### NOTE: when we figure out how to make this loopy, we should reset self.okays before we do this check every time we loop 
    self.okays.clear()

    if self.leader == self.name:
      if (len(self.group.members) > MAX_GROUP): 
      #SPLITTING
        self.req.send_json({"destination": [self.group.leader], "type": "START", "key": "SPLIT_ID"})
                             
      elif (len(self.group.members) + len(self.lgroup.members)) < MAX_GROUP:
      #MERGING LEFT
        self.req.send_json({"destination": [self.group.leader], "type": "START", "key": "MERGE_ID"})
      elif ((len(self.group.members) + len(self.rgroup.members)) < MAX_GROUP):
      #MERGING RIGHT
        self.req.send_json({"destination": [self.group.leader], "type": "START", "key": "MERGE_ID"})

  def handle_broker_message(self, msg_frames):
    '''
    Nothing important to do here yet.
    '''
    pass

  def forwardTo(self, k):
    lBound = self.group.key[0]
    rBound = self.group.key_range[1]
    # L < R
    if ( lBound < rBound):
      if lBound < k and k < rBound:
        return group.leader
      elif k < lBound and k < rBound:
        return group.pred_g.leader
      elif rBound < k and lBound < k:
        return group.succ_g.leader
      else:
        #error
        pass
      # R < L
      elif ( rBound < lBound):
        if lBound < k and k < MAX_KEY:
          return group.leader
        elif MIN_KEY < k and k < rBound:
          return group.pred_g.leader
        elif rBound < k and k < lBound:
          return group.succ_g.leader
        else:
          #error
          pass

  def groupInfo_from_leader(self,leader):
    if self.rgroup.leader == leader:
      return self.rgroup
    elif self.lgroup.leader == leader:
      return self.lgroup
    else:
      #error
      return

  def handle(self, msg_frames):
    assert len(msg_frames) == 3
    assert msg_frames[0] == self.name
    # Second field is the empty delimiter
    msg = json.loads(msg_frames[2])
    typ = msg['type']

    if msg['type'] in ["PROPOSE", "PREPARE", "ACCEPT", "ACCEPTED", "REJECTED", "LEARN"]:
      print "THIS IS A PAXOS MESSAGE"
      self.handle_paxos(msg)
      return
    if msg['type'] in ["START","START_PAXOSED","READY","YES","NO","COMMIT"]:
      print "THIS IS A 2PC MESSAGE"
      if self.name != self.group.leader:
        #fwd to leader
        msg["destination"] = [self.group.leader]
        self.req.send_json(msg)
        return
      elif self.twoPC_contact != msg["source"]:
        self.req.send_json({'type': 'WAIT', 'source': self.name})
        return
      else: 
        self.handle_2pc(msg)
        return

    ####################################################
    #---------- MISC SETUP/FAILURE COMMANDS -----------#
    ####################################################

    ######################
    #### HELLO & SPAM ####
    ######################
    if typ == 'hello':
      if not self.connected:
        self.connected = True
        self.req.send_json({'type': 'helloResponse', 'source': self.name})
        # if we're a spammer, start spamming!
        if self.spammer:
          self.loop.add_callback(self.send_spam)

    elif typ == 'spam':
      self.req.send_json({'type': 'log', 'spam': msg})

    ####################################################
    #---------- DHT BASIC COMMANDS AND REQS -----------#
    ####################################################

    #############
    #### GET ####
    #############
    elif typ = 'get' or typ = 'getRelay':
      k = msg['key']

      dest = self.forwardTo(k)

      if dest = self.leader:
          try:
            v = self.store[k]
            self.req.send_json({'type': 'log', 'debug': {'event': 'getting', 'node': self.name, 'key': k, 'value': v}})
            self.req.send_json({'type': 'getResponse', 'id': msg['id'], 'value': v})
          except KeyError:
            print "Oops! That is not a key for which we have a value. Try again..."
      else:
        self.req.send_json({'type' : 'getRelay', 'destination': [dest],'id' : msg['id'], 'key': msg['key']})

    #############
    #### SET ####
    #############
    elif typ = 'set' or typ = 'setRelay':
      k = msg['key']
      v = msg['value']

      dest = self.forwardTo(k)

      if dest = self.leader:
        self.req.send_json({'type': 'PROPOSE', 'destination': [self.group.leader], 'key': k, 'value': v, 'prior': None})
        self.req.send_json({'type': 'log', 'debug': {'event': 'setting', 'node': self.name, 'key': k, 'value': v}})
        self.req.send_json({'type': 'setResponse', 'id': msg['id'], 'value': v}) 
      else:
        self.req.send_json({'type' : 'setRelay', 'destination': [dest],'id' : msg['id'], 'key': msg['key'], 'value' = msg['value']})
        

  def handle_paxos(self, msg):
    majority = math.ceil(len(self.group.members) / 2)
    typ = msg["type"]
    key = msg["key"]
    n = msg["p_num"]
    self.accs = [m for m in self.group.members if m != self.name]
    if self.group.leader == self.name:
        if typ == "PROPOSE":        
            if self.group.p_num not in self.proposals:
                self.proposals[self.group.p_num] = msg["value"]
            for member in self.accs:
                new_msg = make_paxos_msg("PREPARE", [member], [self.name], key, msg["value"], self.group.p_num, None)
                self.req.send_json(new_msg)
            self.promises[self.group.p_num] = []
            self.group.p_num += 1

        elif typ == "PROMISE":
            if n not in self.promises:
                self.promises[n] = [] #this actually should be an error
            if (msg["prior_proposal"]):
                self.promises[n].append(msg["prior_proposal"])
            else:
                self.promises[n].append((msg["value"], n))

            if (len(self.promises[n]) == majority):
                pick_tup = sorted(self.promises[n], key-lambda x: x[1])[0]
                
                for member in self.accs:
                    new_msg = make_paxos_msg("ACCEPT", [member], [self.name], key, msg["value"], n, None)
                    self.req.send_json(new_msg)
                
        elif typ == "REJECTED":
            if n in self.rejects:
                self.rejects[n].append((msg["value"], n))
            else:
                self.rejects[n] = [(msg["value"], n)]

            if (len(self.rejects[n]) == majority):
                if self.group.p_num not in self.proposals: 
                    self.proposals[self.group.p_num] = msg["value"]
                for member in self.accs:
                    new_msg = make_paxos_msg("PREPARE", [member], [self.name], key, msg["value"], self.group.p_num, None)
                    self.req.send_json(new_msg)
                self.promises[self.group.p_num] = []
                self.group.p_num += 1
                
        elif typ == "ACCEPTED":
            if n in self.accepts:
                self.accepts[n].append((msg["value"], n))
            else:
                self.accepts[n] = [(msg["value"], n)]

            if (len(self.accepts[n]) == majority):
                if n not in self.props_accepted:
                    self.props_accepted[msg.n] = (self.proposals[n], msg["value"])
                    if key == "START":
                        self.req.send_json({"type": "START_PAXOSED", "destination": [self.group.leader], 
                                            "source": [self.name], "value": msg["value"], "key": key})
                    elif key == "READY":
                        self.req.send_json({"type": "READY_PAXOSED", "destination": [self.group.leader], 
                                            "source": [self.name], "value": msg["value"], "key": key})
                    elif key == "YES":
                        self.req.send_json({"type": "YES_PAXOSED", "destination": [self.group.leader], 
                                            "source": [self.name], "value": msg["value"], "key": key})
                    else:
                        for member in self.accs:
                            new_msg = make_paxos_msg("LEARN", [member], [self.name], key, msg["value"], n, None)
                            self.req.send_json(new_msg)
                        
        elif typ == "REDIRECT":
            if key not in self.redirects:
                self.redirects[key] = []
            if n not in self.redirects[key]:
                self.redirects[key].append(n)
                new_msg = make_paxos_msg("PROPOSE", msg["source"], [self.name], key, msg["value"], n, None)
        else:
            print "This is not the typ eof message a proposer should be recieving"
    else:
        if typ == "PREPARE":
            self.group.p_num += 1
            if key not in self.n_int:
                self.n_int[msg.key] = -1 #initialize
            if n >= self.n_int[key]:
                if key in self.acced: # proposals that have been accepted for that key
                    high_p = sorted(self.acced[key], key=lambda x: x[1])[-1]
                    self.n_int[msg.key] = high_p[1] #send the latest (greatest) n
                else:
                    high_p = None
                    self.n_int[key] = n
                new_msg = make_paxos_msg("PROMISE", msg["source"], [self.name], msg["value"], n, high_p)
                self.req.send_json(new_msg)
        elif typ == "ACCEPT":
            if self.n_int[key] <= n:
                new_msg = make_paxos_msg("ACCEPTED", msg["source"], [self.name], msg["value"], n, None) 
                if key not in self.acced:
                    self.acced[key] = []
                self.acced[key].append((msg["value"], n))
            else:
                new_msg = make_paxos_msg("REJECTED", msg["source"], self.name, msg["value"], n, None)
            self.req.send_json(new_msg)
                                      
        elif typ == "LEARN":
            if key == ELECTION_ID:
                self.group.leader = msg["value"]
                self.leaderLease = dt.now() + LEADER_LEASE_TIME
                del self.acced[ELECTION_ID]
            elif key == ADD_ID:
                pass
            elif key == "GROUPS":
                self.lgroup = msg["value"][0]
                self.group = msg["value"][1]
                self.rgroup = msg["value"][2]
                self.store = self.store.extend(msg["store"]) 
           
            else:
                self.store[long(key)] = msg["value"]
        else:
            print "This is not the type of message an acceptor should be receiving"

  def send_spam(self):
    '''
    Periodically send spam, with a counter to see which are dropped.
    '''
    if not hasattr(self, 'spam_count'):
      self.spam_count = 0
    self.spam_count += 1
    t = self.loop.time()
    self.req.send_json({'type': 'spam', 'id': self.spam_count, 'timestamp': t, 'source': self.name, 'destination': self.peer_names, 'value': 42})
    self.loop.add_timeout(t + 1, self.send_spam)

  def shutdown(self, sig, frame):
    self.loop.stop()
    self.sub_sock.close()
    self.req_sock.close()
    sys.exit(0)

def make_paxos_msg(typ, dst, src, key, value, p_num, prior_proposal):
    return {"type": typ, "destination": dst, "source": src, "key": key, "value": value, 
            "p_num": p_num, "prior_proposal": prior_proposal}

if __name__ == '__main__':
  import argparse
  parser = argparse.ArgumentParser()
  parser.add_argument('--pub-endpoint',
      dest='pub_endpoint', type=str,
      default='tcp://127.0.0.1:23310')
  parser.add_argument('--router-endpoint',
      dest='router_endpoint', type=str,
      default='tcp://127.0.0.1:23311')
  parser.add_argument('--node-name',
      dest='node_name', type=str,
      default='test_node')
  parser.add_argument('--spammer',
      dest='spammer', action='store_true')
  parser.set_defaults(spammer=False)
  parser.add_argument('--peer-names',
      dest='peer_names', type=str,
      default='')
  args = parser.parse_args()
  args.peer_names = args.peer_names.split(',')
  args.pred_group = args.prev_group.split(',')
  args.succ_group = args.succ_group.split(',')
  Node(args.node_name, args.pub_endpoint, args.router_endpoint, args.spammer, args.peer_names, args.pred_group, args.succ_group).start()

