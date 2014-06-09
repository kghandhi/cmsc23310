import json
import sys
import signal
import zmq
import time
import math
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
    
  def handle_merge(self, other):
    pass

  def handle_add_node():
    pass

  def handle_drop_node():
    pass


class Node(object):
  def __init__(self, node_name, pub_endpoint, router_endpoint, spammer, peer_names):
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
    self.key = None #should be a key range tuple (lb, ub]
    
    self.lgroup = None #group object
    self.rgroup = None #group object
    self.group = None #group object
    
    self.store = {}
    self.values = {}
    
    self.leader = None
    self.leaderLease = dt.now
    self.proposer = None
    self.acceptor = None

    self.spammer = spammer
    self.peer_names = peer_names
    self.okays = {} #dictionary of okays received hashed on "MERGE": (merge_type, source) or "SPLIT": int
  
    for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
      signal.signal(sig, self.shutdown)

  def handle_join():
    pass

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
      if self.twoPC_contact != msg["source"]:
        self.req.send_json({'type': 'WAIT', 'source': self.name})
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
        
    ##################################################
    #---------- Two Phase Commit Handling -----------#
    ##################################################

    #######################
    #### START + PAXOS ####
    #######################
    elif typ == "START":
        #START PAXOS ON INTERPROCESS (keys: MERGE_REQ, MERGE_ID, SPLIT, value:START)
        #ONCE PAXOS FINISHED, SEND READY ( in )
        #BLOCK
        self.req.send_json({"destination": [self.group.leader], "type": "PROPOSE", "key": "START", "value": ,msg["value"]})

    elif typ == "START_PAXOSED":
      #IN LEARN PHASE, SEND_PAXOSED to LEADER
      #type start_paxosed, key start, value split,merge_id

      if msg["value"] == "SPLIT_ID":
        new_msg = {"type": "READY", "destination": [self.lgroup.leader], "source": [self.name], "key": "SPLIT", "value": "SPLIT_ID"}
        self.req.send_json(new_msg)
        new_msg["destination"] = [self.rgroup.leader]
        self.req.send_json(new_msg)

      elif msg["key"] == "MERGE_ID":
        if len(self.group.members) + len(self.lgroup.members) < MAX_GROUP and len(self.lgroup.members) < len(self.rgroup.members):
           #new_msg1 = {"type": "READY", "destination": [self.lgroup.leader], "source": [self.name], "key": "MERGE_REQ", "value": "READY"}
           new_msg2 = {"type": "READY", "destination": [self.rgroup.leader], "source": [self.name], "key": "MERGE_ID", "value": "READY"}
        elif len(self.group.members) + len(self.rgroup.members) < MAX_GROUP :
           #new_msg1 = {"type": "READY", "destination": [self.rgroup.leader], "source": [self.name], "key": "MERGE_REQ", "value": "READY"}
           new_msg2 = {"type": "READY", "destination": [self.lgroup.leader], "source": [self.name], "key": "MERGE_ID", "value": "READY"}
        else:
          #dont merge
          return

        #self.req.send_json(new_msg1)
        self.req.send_json(new_msg2)

    elif typ == "READY":
      pass

    elif typ == "READY_PAXOSED":
      pass

    elif typ == "YES":
      #type yes, key split,merge, val split,merge_id,merge_req,merge_fwd
      if msg["key"] == "MERGE_REQ":
        if msg["source"][0] == self.lgroup.leader:
          self.group = merge("left")
          self.lgroup = msg["newNeighbor"]
          neighbor = self.rgroup.leader
          which = "leftMerge"

        elif msg["source"][0] == self.rgroup.leader:
          self.group = merge("right")
          self.rgroup = msg["newNeighbor"]
          neighbor = self.lgroup.leader
          which = "rightMerge"
        else:
          print "NOT LEADER OF GROUP??"
          neighbor = None
          pass
  

        learn_msg = ({"destination": self.group.members, "source" : [self.name], "type": "LEARN", "key": "GROUPS", "value": (self.lgroup,self.group,self.rgroup)})
        self.req.send_json(learn_msg)

        commit_msg = ({"destination": msg["source"], "type": "COMMIT", "key": "MERGE_REQ", "value": (self.lgroup,self.group,self.rgroup)})
        self.req.send_json(commit_msg)

        neighbor_msg = ({"destination": [neighbor], "type": "COMMIT", "key": "MERGE_ID","which": which, "value": (self.group)})
        self.req.send_json(neighbor_msg)

        neighbor2_msg = ({"destination": [neighbor], "type": "COMMIT", "key": "MERGE_FWD","which": which, "value": (self.group)})
        self.req.send_json(neighbor2_msg)

      else:
        self.req.send_json({"destination": [self.group.leader], "type": "PROPOSE", "key": "YES","value": msg["value"]})

    elif typ == "YES_PAXOSED":
      if msg["key"] == "SPLIT":
        ###############################33
        #################################33
        #################################
        # IF 2nd YES....
        # SEND LEFT NEIGHBOR LEFT GROUP
        # SEND RIGHT NEIGHBOR RIGHT GROUP
        # SPLIT AND UPDATE INTERNAL GROUPS
        pass
      elif msg["key"] == "MERGE_ID":
        new_msg = {"type": "READY", "destination": [self.lgroup.leader], "source": [self.name], "key": "MERGE", "value": "MERGE_REQ"}
        self.req.send_json(new_msg)

      elif msg["key"] == "MERGE_FWD":
        if msg["source"][0] == self.rgroup.leader:
          groupInfo = self.rgroup
          dest = self.lgroup.leader
        elif msg["source"][0] == self.lgroup.leader:
          groupInfo = self.lgroup
          dest = self.rgroup.leader
        else:
          #ERROR
          pass
        new_msg = {"type": "YES", "destination": [dest], "source": [self.name], "key": "MERGE", "value": "MERGE_REQ", "newNeighbor" : groupInfo}
        self.req.send_json(new_msg)


    ###############
    #### READY ####
    ###############
    elif typ == "READY":
      self.req.send_json({"destination": [self.group.leader], "type": "PROPOSE", "key": "READY", "value": msg["value"]})

    elif typ == "READY_PAXOSED":
        if msg["key"] == "SPLIT":
          response = {"destination": msg["source"], "source": [self.name], "type" : "YES", "key": "SPLIT", "value": "SPLIT"}
        elif msg["key"] == "MERGE":
          response = {"destination": msg["source"], "source": [self.name], "type" : "YES", "key": "MERGE", "value": msg["value"]}
      self.req.send_json(response) 

    #######################
    ###### NO & WAIT ######
    #######################
    elif typ == "NO" or typ == "WAIT":
      self.loop.add_timeout(time.time() + .5, lambda: self.req.send_json({"type": "START", "destination":[self.group.leader], "source": [self.name], "key": msg["key"], "value": msg["value"]}))
    ################
    #### COMMIT ####
    ################
    elif typ == "COMMIT":
        '''
        if msg["key"] == "SPLIT":
          response = {"destination": msg["source"], "source": [self.name], "type" : "YES", "key": "SPLIT", "value": "SPLIT"}
        elif msg["key"] == "MERGE_ID":
          response = {"destination": msg["source"], "source": [self.name], "type" : "YES", "key": "MERGE", "value": msg["value"]}
        elif msg["key"] == "MERGE_REQ":
          response = {"destination": msg["source"], "source": [self.name], "type" : "YES", "key": "MERGE", "value": "MERGE_REQ"}
        elif msg["key"] == "MERGE_FWD":
          response = {"destination": msg["source"], "source": [self.name], "type" : "YES", "key": "MERGE", "value": "MERGE_FWD"}
        self.req.send_json(response) 
        #when this is committed and its a merge, make sure to pass on a new left or right group in paxos with a propose message
        self.req.send_json({"type": "PROPOSE", "destination": [self.group.leader], "key": msg["key"], "value": msg["value"]})
        '''
    ################################################
    #--------------- UNKNOWN EVENT ----------------#
    ################################################
    else:
      self.req.send_json({'type': 'log', 'debug': {'event': 'unknown', 'node': self.name}})

               

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

  Node(args.node_name, args.pub_endpoint, args.router_endpoint, args.spammer, args.peer_names).start()

