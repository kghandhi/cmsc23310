import json
import sys
import signal
import zmq
from datetime import datetime as dt
from datetime import timedelta
from zmq.eventloop import ioloop, zmqstream
ioloop.install()

MAX_GROUP = 10
MIN_GROUP = 4
MAX_KEY = int('f'*128, 16)

class Group(object):
  def __init__(self, key_range, leader, members):
    self.key_range = key_range
    self.leader = leader
    self.members = members
    
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

  def handle(self, msg_frames):
    assert len(msg_frames) == 3
    assert msg_frames[0] == self.name
    # Second field is the empty delimiter
    msg = json.loads(msg_frames[2])
    typ = msg['type']


    if typ == 'get':
      # TODO: handle errors send along to the correct key range 
      k = msg['key']
      if (k <= self.group.key_range[1]) and (k > self.group.key_range[0]):
        try:
          v = self.store[k]
          self.req.send_json({'type': 'log', 'debug': {'event': 'getting', 'node': self.name, 'key': k, 'value': v}})
          self.req.send_json({'type': 'getResponse', 'id': msg['id'], 'value': v})
        except KeyError:
          print "Oops! That is not a key for which we have a value. Try again..."
      elif (k <= self.group.key_range[0]): #find out the highest value of a hash in sha1...
        self.req.send_json({'type' : 'getRelay', 'destination': [group.succ_g.leader],'id' : msg['id'], 'key': msg['key']})
      elif (k > self.group.key_range[1]):
        self.req.send_json({'type': 'getRelay', 'destination': [group.pred_g.leader], 'id': msg['id'], 'key': msg['key']})

    elif typ == 'set':
      # TODO: Paxos
      k = msg['key']
      v = msg['value'] 
      #fill in id, src maybe... because well want to pass it..
      self.req.send_json({'type': 'PROPOSE', 'destination': [self.group.leader], 'key': k, 'value': v, 'prior': None})

      self.req.send_json({'type': 'log', 'debug': {'event': 'setting', 'node': self.name, 'key': k, 'value': v}})
      #self.store[k] = v #propose this value?
      #should this be the value we just set with paxos or just a confirmation?
      self.req.send_json({'type': 'setResponse', 'id': msg['id'], 'value': v}) 
    elif typ == 'hello':
      # should be the very first message we see
      if not self.connected:
        self.connected = True
        self.req.send_json({'type': 'helloResponse', 'source': self.name})
        # if we're a spammer, start spamming!
        if self.spammer:
          self.loop.add_callback(self.send_spam)

    #---------- Two Phase Commit Handling -----------#
    if typ == "START":
        self.req.send_json({"destination": [self.group.leader], "type": "PROPOSE", "key": msg["key"], "value": "START"})
        if self.proposer.props_accepted[msg["key"]]:
            self.req.send_json({"type": "READY", "destination": msg["source"], "source": [self.name], "key": msg["key"], "value": msg["value"]})

    elif typ == "READY":
        response = {"destination": msg["source"], "source": [self.name], "key": msg["key"], "value": msg["value"]}
        if msg["key"] != "MERGE_REQ":
            self.req.send_json({"type": "PROPOSE", "destination": [self.group.leader], "key": msg["key"], "value": "READY"})
            
            if self.proposer.props_accepted[msg["key"]]:
                response["type"] = "OK"
            else:
                response["type"] = "NO"
            self.req.send_json(response)
        else:
            new_msg = {"type": "READY", "key": "MERGE_FWD", "value": msg["value"], "source": [self.name]}
            if msg["source"] == [self.lgroup.leader]:
                new_msg["destination"] = self.rgroup.leader
            else:
                new_msg["destination"] = self.lgroup.leader
            self.req.send_json(new_msg)
            
    elif typ == "OK":
        response = {"destination": msg["source"], "source": [self.name], "key": msg["key"], "value": msg["value"]}
        if msg["key"] == "MERGE_FWD":
            #should I paxos here to decide to forward it as an okay? yes probably
            self.req.send_json({"type": "PROPOSE", "destination": [self.group.leader], "key": "MERGE_REQ", "value": "READY"})
            if self.proposer.props_acced[msg["key"]]:
                response["type"] = "OK"
                self.req.send_json(response)
        else:
            if msg["key"] == "MERGE_REQ" or msg["key"] == "MERGE_ID":
                if "MERGE" in self.okays:
                    self.okays["MERGE"].append((msg["key"], msg["source"][0]))
                else:
                    self.okays["MERGE"] = [(msg["key"], msg["source"][0])]
                if len(self.okays["MERGE"]) == 2:
                    to_merge = [x for x in self.okays["MERGE"] if x[0] == "MERGE_REQ"]
                    assert (len(to_merge) == 1)
                    if to_merge[1] == self.lgroup.leader:
                        v = self.handle_merge("left")
                     
                    elif to_merge[1] == self.rgroup.leader:
                        v = self.handle_merge("right")
                    self.okays["MERGE"] = []
            elif msg["key"] == "SPLIT_ID":
                self.okays["SPLIT"] += 1
                if self.okays["SPLIT"] == 2:
                    v = self.handle_split()
                    self.okays["SPLIT"] = 0
                    
                response["type"] = "COMMIT"
                response["value"] = v
                response["destination"] = [self.lgroup.leader]
                self.req.send_json(response)
                response["destination"] = [self.rgroup.leader]
                self.req.send_json(response)

    elif typ == "COMMIT":
        #when this is committed and its a merge, make sure to pass on a new left or right group in paxos with a propose message
        self.req.send_json({"type": "PROPOSE", "destination": [self.group.leader], "key": msg["key"], "value": msg["value"]})

    #--------- PAXOS messages ----------
    elif typ in ["PROPOSE", "PREPARE", "ACCEPT", "ACCEPTED", "REJECTED", "LEARN"]:
      self.handle_paxos(msg)

    elif typ == 'spam':
      self.req.send_json({'type': 'log', 'spam': msg})
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

