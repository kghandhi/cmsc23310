from __future__ import division
import json
import sys
import signal
import zmq
import time
import math
import sha
from datetime import datetime as dt
from datetime import datetime
from datetime import timedelta
from zmq.eventloop import ioloop, zmqstream
ioloop.install()

MAX_GROUP = 10
MIN_GROUP = 2
#MAX_KEY = int('f'*128, 16)
MIN_KEY = 0
MAX_KEY = 48
TIME_LOOP = 2 #how often we house keep

LEADER_LEASE_TIME = timedelta(0,5)

TWOPC_MESSAGES = ["START","START_PAXOSED", "READY","READY_PAXOSED", "YES","YES_PAXOSED",
                  "NO","WAIT","COMMIT"]
TWOPC_UNBLOCKED = ["START_PAXOSED", "READY_PAXOSED","YES_PAXOSED","WAIT"]

PAXOS_MESSAGES = ["PROPOSE","PROMISE", "PREPARE", "ACCEPT", "ACCEPTED", "REJECTED", "LEARN", "REDIRECT"]

DHT_MESSAGES = ["get","getRelay","fwd_getResponse","get_ack","set","setRelay","fwd_setResponse","set_ack"]

LOG_CHANGES = True
LOG_EVERY = False
LOG_MAINTAIN = False
LOG_PAXOS = True
LOG_2PC = True
LOG_SETS = False
BLOCKING = False

class Group(object):
  def __init__(self, key_range, leader, members, p_num):
    self.key_range = key_range #tuple [a,b)
    self.leader = leader
    self.leaderLease = dt.now()
    self.members = members
    self.p_num = p_num #initially 1

  def __repr__(self):
    return "\nGROUP:\nkey_range=[{},{}),\n leader={},\n p_num={},\nmembers={}".format(self.key_range[0], 
                                                                        self.key_range[1], 
                                                                        self.leader, self.p_num, 
                                                                        self.members)
    
    
class Node(object):
  def __init__(self, node_name, pub_endpoint, router_endpoint, spammer, peer_names, 
               key_range, pred_names, key_range1, succ_names, key_range2):
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
   
    self.group = Group((key_range[0], key_range[1]), peer_names[0], peer_names, 1)  #group object   
    self.lgroup = Group((key_range1[0], key_range1[1]), pred_names[0], pred_names, 1) #group object
    self.rgroup = Group((key_range2[0], key_range2[1]), succ_names[0], succ_names, 1) #group object

    self.store = dict()

    self.BLOCK_2PC = None

    # Liveness queues
    self.pending_reqs = []
    self.pong = {} #dict of { (<nodeName>:<rounds_since_ponged>)}


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

  def SEND_MSG(self,msg):
    if msg["type"] == "helloResponse" or msg["type"] == "log":
      self.req.send_json(msg)
      return
    if msg["type"] == "setResponse" or msg["type"] == "getResponse":
      self.req.send_json(msg)
      return

    if "destination" not in msg:
      print "DESTINATION NOT IN MSG",msg
      return
    if type(msg["destination"]) != list:
      print "NOT LIST"
      return 
    if type(msg["destination"][0]) == list:
      print "SHOULD NOT BE LIST OF LISTS"
      return
    self.req.send_json(msg)

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
      half_range = long((b - a) / 2) 
      left_key = (a, half_range + a)
      right_key = (half_range + a, b)

    old_ms = self.group.members
    l_sz = len(old_ms) / 2

    left_ms = [old_ms[i] for i in xrange(int(l_sz))]
    right_ms = [old_ms[i] for i in xrange(int(l_sz), len(old_ms))]

    new_left = Group(left_key, None, left_ms, self.group.p_num)
    new_right = Group(right_key, None, right_ms, self.group.p_num)

    return (new_left, new_right)

  def handle_merge(self, side):
    if LOG_2PC: print "IN HANDLE MERGE"
    if side == "left":
      b = self.group.key_range[1]
      a = self.lgroup.key_range[0]
      new_ms = [x for x in self.group.members]
      new_ms.extend(self.lgroup.members)
      new_p_num = max(self.lgroup.p_num, self.group.p_num)

    elif side == "right":
      a = self.group.key_range[0]
      b = self.rgroup.key_range[1]
      new_ms = [x for x in self.group.members]
      new_ms.extend(self.rgroup.members)
      new_p_num = max(self.rgroup.p_num, self.group.p_num)

    new_group = Group((a,b), None, new_ms, new_p_num)
    return new_group

  def start(self):
    '''
    Simple manual poller, dispatching received messages and sending those in
    the message queue whenever possible.
    '''
    LOG_FILENAME = "logging_" + self.name
    sys.stdout = open(LOG_FILENAME, 'w')


    print "I,",self.name,", AM ALIVE", "\n"
    self.loop.start()
    print "STARTING"
    #self.loop.add_callback(self.housekeeping)

  def housekeeping(self):
    return
    print "\n\nIN HOUSEKEEPING"
    print "MY INFO:",self.lgroup,self.group,self.rgroup
    #######################
    #HEARTBEATS
    #######################
    if self.name == self.group.leader:
      print "PONG CHECK",self.pong
      if not self.pong:
        for mem in self.group.members:
          self.pong[mem] = 0


      for mem in self.pong:
        if mem[1] == 4:
            proposal = {"type": "START", "destination": [self.group.leader], "source": self.name, 
                      "key": "DROP", "value": dead_member}
            self.SEND_MSG(proposal)

      print self.pong
      for mem in self.pong.values():
        print "\t\t",mem
        mem += 1
      for mem in self.pong.keys():
        if mem != self.name:
          ping = {"type": "PING", "destination": [mem], "source": self.name}
          self.SEND_MSG(ping)
          print "SENT PING",ping

    
    ##############################
    #CHECK IF KICKED OUT OF GROUP
    ##############################
    if self.name not in self.group.members:
      plz_add = ({"type": "START", "source": self.name, 
                          "key": "ADD", "value": self.name})

      if self.group.leader:
        plz_add["destination"] = [self.group.leader]
      else:
        plz_add["destination"] = [x for x in self.group.members if x != self.name]
      self.SEND_MSG(plz_add)
      print "KICKED OUT OF GROUP, ASKING TO REJOIN",plz_add
    
    ##########################
    #CHECK GROUPSIZE
    ##########################
    if self.group.leader == self.name:
      # Split if you have too many members
      if (len(self.group.members) > MAX_GROUP):
        self.SEND_MSG({"type": "START", "destination": [self.group.leader], "source": self.name,
                            "key": "SPLIT", "value": "SPLIT"})
      # Merge with a neighbor if you have too few members
      if (len(self.group.members) < MIN_GROUP):
        self.SEND_MSG({"type": "START", "destination": [self.group.leader], "source": self.name,
                            "key": "MERGE", "value": "MERGE_ID"})

    ###############################################
    #CHECK REQ QUEUE TO MAKE SURE GET/SET REQUESTS WERENT DROPPED
    ###############################################
    if self.pending_reqs:
      for unhandled in self.pending_reqs:
        if unhandled[0] == "get":
          handle = {"type": "getRelay", "source": self.name, "destination": [self.group.leader], 
                    "key": unhandled[1]}
        elif unhandled[0] == "set":
          stset, key, value = unhandled
          handle = {"type": "setRelay", "source": self.name, "destination": [self.group.leader], 
                    "key": key, "value": value}
        else:
          commit, key, value, dest = unhandled
          handle = {"type": "COMMIT", "source": self.name, "destination": [dest], "key": key, 
                    "value": value}
        self.SEND_MSG(handle)
        print "RESENDING UNANSWERED REQ",handle
    
    ###########################
    ##### CHECK LEADER STATUS
    ###########################
    if not self.group.leader:
      proposal = {"type": "PROPOSE", "destination": [self.name], "source": self.name,"tpcFROM":self.name, 
                  "key": "ELECTION", "value": self.name, "parent": self.name, "who": None, "p_num":self.group.p_num}
      self.SEND_MSG(proposal)
      print "PROPOSE LEADER CHANGE"
    

    self.loop.add_timeout(time.time() + TIME_LOOP, self.housekeeping)

  def handle_broker_message(self, msg_frames):
    '''
    Nothing important to do here yet.
    '''
    pass

  def forwardTo(self, key):
    lbound = long(self.group.key_range[0])
    rbound = long(self.group.key_range[1])
    key = long(key)
    if (lbound < rbound):
      if lbound <= key and key < rbound:
        if self.group.leader:
          return self.group.leader
        else:
          return self.name
      elif key < lbound:
        if abs((key) - (lbound)) > (key) + (MAX_KEY - rbound):
          return self.rgroup.leader
        else:
          return self.lgroup.leader
      elif key >= rbound:
        if (MAX_KEY - key) + lbound < abs(rbound - key):
          return self.lgroup.leader
        else:
          return self.rgroup.leader
      else:
        raise Exception("This may be a problem with hashing if the key isnt between 0 and max")
    elif (rbound < lbound):
      if (lbound <= key and key <= MAX_KEY) or (MIN_KEY <= key and key < rbound) :
        return self.group.leader
      else:
        if abs(key - rbound) > abs(key - lbound):  
          return self.lgroup.leader
        else:
          return self.rgroup.leader
    else:
      raise Exception("The key_range is Zero")

  def groupInfo_from_leader(self, leader):
    if self.rgroup.leader == leader:
      return self.rgroup
    elif self.lgroup.leader == leader:
      return self.lgroup
    else:
      raise Exception("No leader??")

  def handle(self, msg_frames):
    assert len(msg_frames) == 3
    assert msg_frames[0] == self.name
    # Second field is the empty delimiter

    msg = json.loads(msg_frames[2])
    if LOG_EVERY: print "RECIEVED",msg
    typ = msg['type']


    if typ == "GROUP_MEMBERSHIP":
      #time.sleep(5)
      #self.SEND_MSG({"type":"log","lgroup":groupToDict(self.lgroup),"group":groupToDict(self.group),"rgroup":groupToDict(self.rgroup)})
      return

    if typ in ["hello","spam","PING","PONG"]:
      self.handle_maintainence(msg,typ)

    elif typ in ["COMMIT_ACK"]:
      if LOG_2PC: print "\n", msg["req"]
      for req in self.pending_reqs:
        if LOG_2PC: print req
        if len(req) == 4 and len(msg["req"]) == 4:
          if req[1] == msg["req"][1] and req[3] == msg["req"][3][0]:
            self.pending_reqs.remove(req)
            if LOG_2PC: print "took commit_ack out of pending",msg["req"]
            return
      print "COMMIT_ACK NOT IN PENDING"
 
      return 

    elif typ in PAXOS_MESSAGES:
      if LOG_PAXOS: print self.name , "recieved message: ", msg
      self.handle_paxos(msg)
      return

    elif msg['type'] in TWOPC_MESSAGES:
      if LOG_2PC: print "2pc msg, not yet in handler"
      if self.name != self.group.leader:
        msg["destination"] = [self.group.leader]
        self.SEND_MSG(msg)
        if LOG_2PC: print "FWD'ed msg to leader",msg
      else:# self.BLOCK_2PC == None or self.BLOCK_2PC == (msg["parent"],msg["key"]) or msg["type"] in TWOPC_UNBLOCKED:
        self.handle_2pc(msg)
      '''
      else: 
        print "WE ARE BLOCKED - returned WAIT msg in response to","\n",self.BLOCK_2PC,"\n" , msg
        self.SEND_MSG({'type': 'WAIT', 'source': self.name,"key": msg["key"],
             "value": msg["value"], "destination" : [msg["source"]]})
      '''
      return

    elif typ in DHT_MESSAGES:
      self.handle_get_set(msg,typ)
      return

    else:
      self.SEND_MSG({'type': 'log', 'debug': {'value':msg}})

  #################
  #################
  ####   GET   ####
  ####   SET   ####
  #################
  #################

  def handle_get_set(self,msg,typ):
    if typ == "fwd_getResponse":
      if LOG_SETS: print "IN GETRESPONSE_FWD",msg
      get_respons = ({'type': 'getResponse', 'id': msg['id'], 'value': msg["value"]}) 
      self.SEND_MSG(get_respons)
      print "SENT getResponse TO BROKER",get_respons
      return

    elif typ == 'get' or typ == 'getRelay':
      if LOG_SETS: print "MESSAGE: GET", msg["key"]
      k = msg['key']

      if typ == "get":
        parent = (self.name, msg["id"])
       
      else:
        parent = msg["parent"]

      self.pending_reqs.append(("get", k))

      dest = self.forwardTo(k)

      if dest == self.group.leader or dest == self.name:

        try:
          v = self.store[long(k)]
          if typ == "get":
            self.SEND_MSG({'type': 'getResponse', 'id': msg['id'], 'value': v})
            if LOG_SETS: print "sent msg", {'type': 'getResponse', 'id': msg['id'], 'value': v}
          else:
            self.SEND_MSG({'type': 'fwd_getResponse', "destination":[msg["parent"][0]], 'id': msg["parent"][1], 'value': v})
            if LOG_SETS: print "sent msg", ({'type': 'fwd_getResponse', "destination":[msg["parent"][0]], 'id': msg["parent"][1], 'value': v})

        except KeyError:
          print "Oops! That is not a key for which we have a value. Try again..."
      else:
        self.SEND_MSG({'type' : 'getRelay', 'parent' : parent, 'destination': [dest],
                           'id' : msg['id'], 'key': msg['key'],"source":self.name})
        if LOG_SETS: print "sent getRelay",({'type' : 'getRelay', 'parent' : parent, 'destination': [dest],
                           'id' : msg['id'], 'key': msg['key']})
      if typ == "getRelay":
        if LOG_SETS: print "in getRelay"
        if LOG_SETS: print msg
        get_ack = ({"destination": [msg["source"]], "source": self.name, "parent" : parent,
                           "type": "get_ack", "req": ("get", k)})
        if LOG_SETS: print get_ack
        self.SEND_MSG(get_ack)
        if LOG_SETS: print "sent get_ack",get_ack 

    elif typ == "get_ack":
      if msg["req"] in self.pending_reqs:
        self.pending_reqs.remove(msg["req"])

    #############
    #### SET ####
    #############
    elif typ == "fwd_setResponse":
      if LOG_SETS: print "IN SETRESPONSE_FWD"
      set_respons = ({'type': 'setResponse', 'id': msg['id'], 'value': msg["value"]}) 
      self.SEND_MSG(set_respons) 
      print "SENT setResponse TO BROKER",set_respons,"\n"

    elif typ == 'set' or typ == 'setRelay':
      if LOG_SETS: print "MESSAGE: SETRELAY",msg["key"],"to",msg["value"]
      k = msg['key']
      v = msg['value']

      if typ == "set":
        parent = (self.name,msg["id"])
        tpcFROM = self.name
      else:
        parent = msg["parent"]
        tpcFROM = msg["source"]


      self.pending_reqs.append(("set", k, v))
      dest = self.forwardTo(k)

      if dest == self.group.leader or dest == self.name:
        propose_paxos = ({'type': 'PROPOSE', 'destination': [self.group.leader], 'key': k, "who": self.name, 
                          'value': v,"tpcFROM":tpcFROM, 'prior': None, "p_num": self.group.p_num, "parent":parent})

        self.SEND_MSG(propose_paxos)
        
        self.pending_reqs.remove(("set", k, v))
        if LOG_2PC: print "SENT PROPOSE?",propose_paxos,"\n",msg
        #self.SEND_MSG({"type":"log", "check":propose_paxos})
      else:
        setRelay_msg = ({'type' : 'setRelay', 'destination': [dest],'id' : msg['id'], 
                            'key': msg['key'], 'value' : msg['value'], "parent":parent, "source":self.name})
        self.SEND_MSG(setRelay_msg)
        if LOG_SETS: print "SENT SETRELAY",setRelay_msg

      if typ == "setRelay":
        self.SEND_MSG({"type": "set_ack", "destination": [msg["source"]], 
                            "source": self.name, "req": ("set", k, v), "parent":parent})
      if LOG_SETS: print "END OF SET/SETRELAY"
      return
    elif typ == "set_ack":
      if LOG_SETS: print "RECIEVED SET_ACK",msg
      if msg["req"] in self.pending_reqs:
        self.pending_reqs.remove(msg["req"])

    return

  def handle_maintainence(self,msg,typ):
    if typ == 'hello':
      if not self.connected:
        self.connected = True
        self.loop.add_callback(self.housekeeping)
        self.SEND_MSG({'type': 'helloResponse', 'source': self.name})
        print self.name,"sent message",{'type': 'helloResponse', 'source': self.name},"\n"
        # if we're a spammer, start spamming!
        if self.spammer:
          self.loop.add_callback(self.send_spam)
      return

    elif typ == 'spam':
      self.SEND_MSG({'type': 'log', 'spam': msg})
      return

    elif typ == "PING":
      if LOG_MAINTAIN: print "RECIEVED PING",msg

      pong = {"type": "PONG", "destination": [msg["source"]], "source": self.name, "value":None}
      self.SEND_MSG(pong)
      if LOG_MAINTAIN: print "SENT PONG",pong
      return

    elif typ == "PONG":
      if LOG_MAINTAIN: print "RECIEVED PONG",msg
      if LOG_MAINTAIN: print self.pong,msg["source"]
      if msg["source"] in self.pong:
        self.pong[msg["source"]] = 0
      else:
        if LOG_MAINTAIN: print "received pong, not in"
      if LOG_MAINTAIN: print "\tSURVIVED PONG",self.pong
      return    

  #################################
  #######    HANDLE         #######
  ##########    PAXOS   ###########
  #################################

  def handle_paxos(self, msg):
    if LOG_PAXOS: print "\n"
    if LOG_PAXOS: print "RECEIVED PAXOS MESSAGE",msg["type"],msg
    majority = math.ceil(len(self.group.members) / 2)
    typ = msg["type"]
    key = msg["key"]
    n = msg["p_num"]
    self.accs = [m for m in self.group.members]
    if (self.group.leader == self.name or key == "LEADER") and typ not in ["LEARN","PREPARE","ACCEPT"]:
      if typ == "PROPOSE":       
          if self.group.p_num not in self.proposals:
            self.proposals[self.group.p_num] = msg["value"]
          for member in self.accs:
              new_msg = make_paxos_msg("PREPARE", [member], self.name, key, msg["value"], 
                                       self.group.p_num, None, msg["parent"], msg["who"], msg["tpcFROM"])

              self.SEND_MSG(new_msg)
              if LOG_PAXOS: print "SENT PAXOS MESSAGE",new_msg
          self.promises[self.group.p_num] = []
          self.group.p_num += 1

      elif typ == "PROMISE":
          if LOG_PAXOS: print "IN PROMISE",n,self.promises
          if n not in self.promises:
            if LOG_PAXOS: print "n not in self.promises",msg["prior_proposal"]
            self.promises[n] = [] #this actually should be an error
          if (msg["prior_proposal"]):
              self.promises[n].append(msg["prior_proposal"])
          else:
              self.promises[n].append((msg["value"], n))

          if (len(self.promises[n]) == majority):
              pick_tup = sorted(self.promises[n], key=lambda x: x[1])[0]
              
              for member in self.accs:
                #def make_paxos_msg(typ, dst, src, key, value, p_num, prior_proposal, parent, who):
                new_msg = make_paxos_msg("ACCEPT", [member], self.name, key, msg["value"], 
                                         n, None, msg["parent"], msg["who"],msg["tpcFROM"])
                self.SEND_MSG(new_msg)
                if LOG_PAXOS: print "SENT ACCEPT",new_msg
                
      elif typ == "REJECTED":
          if n in self.rejects:
            self.rejects[n].append((msg["value"], n))
          else:
            self.rejects[n] = [(msg["value"], n)]

          if (len(self.rejects[n]) == majority):
              if self.group.p_num not in self.proposals: 
                self.proposals[self.group.p_num] = msg["value"]
              for member in self.accs:
                  new_msg = make_paxos_msg("PREPARE", [member], self.name, key, msg["value"], 
                                           self.group.p_num, None, msg["parent"], msg["who"],msg["tpcFROM"])
                  self.SEND_MSG(new_msg)
              self.promises[self.group.p_num] = []
              self.group.p_num += 1
                
      elif typ == "ACCEPTED":
          if LOG_PAXOS: print "IN ACCEPTED",n,self.accepts,majority  
          if n in self.accepts:
            self.accepts[n].append((msg["value"], n))
          else:
            self.accepts[n] = [(msg["value"], n)]
          if (len(self.accepts[n]) == majority):
              if LOG_PAXOS: print "SUCCESSFUL PAXOS",n,self.props_accepted,key
              if n not in self.props_accepted:

                self.props_accepted[n] = (self.proposals[n], msg["value"])

                if key == "START":
                  self.SEND_MSG({"parent": msg["parent"], "type": "START_PAXOSED", "destination": [self.group.leader], 
                            "source": self.name, "value": msg["value"], "key": key, "who": msg["who"],"tpcFROM":msg["tpcFROM"]})
                elif key == "READY":
                  self.SEND_MSG({"parent": msg["parent"], "type": "READY_PAXOSED", "destination": [self.group.leader], 
                              "source": self.name, "value": msg["value"], "key": key, "who": msg["who"],"tpcFROM":msg["tpcFROM"]})
                elif key == "YES":
                  self.SEND_MSG({"parent": msg["parent"], "type": "YES_PAXOSED", "destination": [self.group.leader], 
                                "source": self.name, "value": msg["value"], "key": key, "who": msg["who"],"tpcFROM":msg["tpcFROM"]})
                else:
                  if LOG_PAXOS: print "LEARN ELECTION OR KEY",msg
                  if key == "ELECTION":
                    self.SEND_MSG({"type": "COMMIT", "destination": [self.lgroup.leader, self.rgroup.leader], 
                                        "source": self.name, "value": msg["value"], "key": key, "who": msg["who"]})
                  for member in self.accs:
                    new_msg = make_paxos_msg("LEARN", [member], self.name, key, msg["value"], n, 
                                             None, msg["parent"], msg["who"],msg["tpcFROM"])
                    self.SEND_MSG(new_msg)

                    if LOG_PAXOS: print "SENT LEARN", new_msg

                  setResponse_fwd_msg = ({'type': 'fwd_setResponse', 'destination' : [msg["parent"][0]],"id":msg["parent"][1], 'value': msg["value"], "source":self.name}) 

                  self.SEND_MSG(setResponse_fwd_msg) 
                  if LOG_PAXOS: print "sent ",setResponse_fwd_msg
      elif typ == "REDIRECT":
          if key not in self.redirects:
            self.redirects[key] = []
            if n not in self.redirects[key]:
              self.redirects[key].append(n)
              new_msg = make_paxos_msg("PROPOSE", [msg["source"]], self.name, key, msg["value"], 
                                       n, None, msg["parent"], msg["who"],msg["tpcFROM"])
      else:
          if LOG_PAXOS: print "This is not the type of message a proposer should be recieving"
          self.SEND_MSG({'type': 'log', 'spam': msg})

    else:
      if typ == "PREPARE":
        if LOG_PAXOS: print "IN PREPARE HERE",key,self.n_int,n
        self.group.p_num += 1
        if key not in self.n_int:

          self.n_int[key] = -1 #initialize
        if n >= self.n_int[key]:
            if key in self.acced: # proposals that have been accepted for that key
              if LOG_PAXOS: print "here",self.acced
              high_p = sorted(self.acced[key], key=lambda x: x[1])[-1]
              self.n_int[key] = high_p[1] #send the latest (greatest) n
              if LOG_PAXOS: print "here again",high_p,self.n_int
            else:
              if LOG_PAXOS: print "in else case"
              high_p = None
              self.n_int[key] = n
            if LOG_PAXOS: print "About to make new msg",msg["parent"], msg["who"]
              
            new_msg = make_paxos_msg("PROMISE", [msg["source"]], self.name, msg["key"],msg["value"], 
                                     n, high_p, msg["parent"], msg["who"],msg["tpcFROM"])
            self.SEND_MSG(new_msg)
            if LOG_PAXOS: print "SENT PREPARE",new_msg
      elif typ == "ACCEPT":
          if self.n_int[key] <= n:
            new_msg = make_paxos_msg("ACCEPTED", [msg["source"]], self.name,msg["key"], msg["value"], 
                                     n, None, msg["parent"], msg["who"],msg["tpcFROM"]) 
            if LOG_PAXOS: print "SENT ACCEPTED",msg
            if key not in self.acced:
              self.acced[key] = []
              self.acced[key].append((msg["value"], n))
          else:
              new_msg = make_paxos_msg("REJECTED", [msg["source"]], self.name,msg["key"], msg["value"], 
                                       n, None, msg["parent"], msg["who"],msg["tpcFROM"])
              if LOG_PAXOS: print "SENT REJECTED",msg
          self.SEND_MSG(new_msg)
            
      elif typ == "LEARN":
          if LOG_PAXOS: print "IN LEARN",msg


          if key == "ELECTION":
            if "which" in msg:
              if msg["which"] == "yourRight":
                self.rgroup.leader = msg["value"]
                print "CHANGED R LEADER TO",self.rgroup.leader
              elif msg["which"] == "yourLeft":
                self.lgroup.leader = msg["value"]
                print "CHANGED L LEADER TO",self.lgroup.leader
              return
            else:

              self.group.leader = msg["value"]

              self.group.leaderLease = dt.now() + LEADER_LEASE_TIME
              if LOG_CHANGES: print "CHANGED LEADER TO",self.group.leader
              del self.acced["ELECTION"]

          elif key == "GROUPS":
            if LOG_2PC: print "learn group msg",msg
            if LOG_2PC:print "\n\n\n\n"
            self.lgroup = dictToGroup( msg["value"][0] )
            self.group = dictToGroup( msg["value"][1] )
            self.rgroup = dictToGroup( msg["value"][2] )
            self.store = dict(self.store.items() + msg["store"].items())

            if LOG_CHANGES:
              print "new L Group",self.lgroup.members
              print "my new Group",self.group.members
              print "new R Group",self.rgroup.members
              print "my store",self.store

            #self.SEND_MSG( {"type":"log","GROUP_CHANGE": {"lgroup":groupToDict(self.lgroup),"group":groupToDict(self.group),"rgroup":groupToDict(self.rgroup)} })

          elif key == "BLOCK":
            self.BLOCK_2PC = (msg["parent"], msg["value"])
            print "BLOCKED ON "(msg["parent"], msg["value"])
            return

          elif key == "UNBLOCK":
            self.BLOCK_2PC = None

          elif key == "ADD_SELF":
            self.lgroup = dictToGroup( msg["value"][0] )
            self.group = dictToGroup( msg["value"][1] )
            self.rgroup = dictToGroup( msg["value"][2] )
            self.store = dict(self.store.items() + msg["store"].items())

            if LOG_CHANGES:
              print "new L Group",self.lgroup.members
              print "my new Group",self.group.members
              print "new R Group",self.rgroup.members
              print "my store",self.store

          elif key == "ADD_OTHER":
            if LOG_2PC: print "IN ADD OTHER",msg
            if msg["which"] == "yourRight":
              self.rgroup.members.append(msg["value"])
              if LOG_CHANGES: print "ADDED",msg["value"],"to R"#,self.rgroup
            elif msg["which"] == "yourLeft":
              self.lgroup.members.append(msg["value"])
              if LOG_CHANGES: print "ADDED",msg["value"],"to L"#,self.lgroup
            else:
              raise Exception("Well which group has changed?") 

          elif key == "DROP_OTHER":
            if msg["which"] == "yourRight":
              self.rgroup.members.remove(msg["value"])
              if LOG_CHANGES: print "Dropped",msg["value"],"from R Group"#,self.rgroup
            elif msg["which"] == "yourLeft":
              self.lgroup.members.remove(msg["value"])
              if LOG_CHANGES: print "Dropped",msg["value"],"from L Group"#,self.lgroup
            else:
              raise Exception("Well which group has changed?")

          elif key == "DROP_SELF":
            self.group.members.remove(msg["value"])
            if LOG_CHANGES: print "Dropped",msg["value"],"from group"#,self.group

          else:
            print "UPDATING STORE", key, msg["value"],"\n"
            if LOG_PAXOS: print "UPDATED STORE"
            self.store[long(key)] = msg["value"]
      else:
          if LOG_PAXOS: print "This is not the type of message an acceptor should be receiving"

  #################
  #################
  ####  HANDLE  ###
  ####   2PC   ####
  #################
  #################

  def handle_2pc(self, msg):
    typ = msg["type"]
    if LOG_2PC: print "GOT 2pc msg",msg
     ###############
     #### START ####
     ###############
    if typ == "START":
      if LOG_2PC: print "2PC START",msg
      # INPUT type "START" , dest leader , source name , key SPLIT/MERGE/ADD/DROP , value SPLIT/MERGE_ID/NAME/NAME

      if msg["key"] == "SPLIT":
        if (self.group.members) <= MIN_GROUP:
          return

      if BLOCKING:
        block_msg = ({"parent" : self.name ,"destination": self.group.members, "type": "LEARN",
                            "key": "BLOCK", "value": msg["value"],"p_num":self.group.p_num})
        self.SEND_MSG(block_msg)
        print "sent block",block_msg

      if "source" not in msg:
        msg["source"] = self.name

      paxos_start = ({"parent" : self.name ,"destination": [self.group.leader], "type": "PROPOSE","tpcFROM":msg["source"],
                          "key": "START", "value": msg["key"] , "who" : msg["value"],"p_num":self.group.p_num})

      self.SEND_MSG(paxos_start)
      if LOG_2PC: print "sent start to paxos",paxos_start
      
     #######################
     #### START_PAXOSED ####
     #######################
    elif typ == "START_PAXOSED":
      if LOG_2PC: print "2PC START PAXOSED",msg
      #INPUT type start_paxosed, key start, value split/merge/add/drop , who split/merge_id/name/name
      if msg["value"] == "SPLIT" or msg["value"] == "ADD" or msg["value"] == "DROP" or msg["value"] == "ELECTION":
        if LOG_2PC: print "IN ADD"
        new_msg = { "parent":msg["parent"] ,"type": "READY", "destination": [self.lgroup.leader],
                    "source": self.name, "key": msg["value"], "value": msg["who"] }
        self.SEND_MSG(new_msg)
        if LOG_2PC: print "sent READY left",new_msg

        new_msg["destination"] = [self.rgroup.leader]
        self.SEND_MSG(new_msg)
        if LOG_2PC: print "sent READY right",new_msg
        return

       ################
       #### MERGE #####
       ################
      elif msg["value"] == "MERGE":
        if LOG_2PC: print "IN START_PAXOSED - MERGE",msg
        if len(self.group.members) + len(self.lgroup.members) < MAX_GROUP and len(self.lgroup.members) < len(self.rgroup.members):
          new_msg = { "parent":msg["parent"] ,"type": "READY", "destination": [self.rgroup.leader],
                      "source": self.name, "key": "MERGE", "value": "MERGE_ID"}
        elif len(self.group.members) + len(self.rgroup.members) < MAX_GROUP :
          new_msg = { "parent":msg["parent"] ,"type": "READY", "destination": [self.lgroup.leader], 
                      "source": self.name, "key": "MERGE", "value": "MERGE_ID" }
        else:
            #dont merge
          print "DONT MERGE"

          if BLOCKING: new_msg =({"parent" : self.name ,"destination": [self.group], "type": "LEARN",
                                 "key": "UNBLOCK", "value": msg["who"],"p_num":self.group.p_num})

        self.SEND_MSG(new_msg)
        if LOG_2PC: print "sent msg",new_msg
     ###############
     #### READY ####
     ###############
    elif typ == "READY":
      if LOG_2PC: print "RECEIVED READY",msg
      # type READY , key split/merge/add/drop , value split/MERGE_ID/ / /name/name
      ready_paxos = ({"parent" : msg["parent"] , "source": self.name, "destination": [self.group.leader],"tpcFROM":msg["source"], 
                "type": "PROPOSE", "key": "READY", "value": msg["key"] , "who" : msg["value"],"p_num":self.group.p_num})
      self.SEND_MSG(ready_paxos)
      if LOG_2PC: print "SENT READY to PAXOS",ready_paxos
     #######################
     #### READY_PAXOSED ####
     #######################
    elif typ == "READY_PAXOSED":
      if LOG_2PC: print "RECEIVED READY_PAXOSED",msg
      # type ready_paxosed, key ready , value split,merge_id/add/drop, who split/merge_id/merge_req/merge_id/name/name

       #########################
       #### SPLIT,ADD,DROP #####
       #########################
      if msg["value"] in ["SPLIT","ADD","DROP","ELECTION"]:
        if BLOCKING:
          block_paxos = ({"parent" : msg["parent"] ,"source": self.name, "destination": [self.group.leader], 
                              "type": "LEARN", "key": "BLOCK", "value": msg["value"],"p_num":self.group.p_num})
          self.SEND_MSG(block_paxos)
          print "paxos block",block_paxos

        response = {"parent":msg["parent"] ,"destination": [msg["parent"]], "source": self.name, 
                    "type" : "YES", "key": msg["value"], "value": msg["who"]}
       ################
       #### MERGE #####
       ################
      elif msg["value"] == "MERGE":
        if BLOCKING:
          block_paxos = ({"parent" : msg["parent"], "source": self.name, "destination": [self.group.leader], 
                              "type": "LEARN", "key": "BLOCK", "value": "MERGE","p_num":self.group.p_num})
          self.SEND_MSG(block_paxos)
          print "sent paxos block",block_paxos
        ###################
        #### MERGE_ID #####
        ###################
        if msg["who"] == "MERGE_ID":
          if LOG_2PC: print "respond yes from merge_id"
          response = { "parent":msg["parent"] ,"destination": [msg["parent"]], "source": self.name, 
                       "type" : "YES", "key": "MERGE", "value": "MERGE_ID"}
          self.SEND_MSG(response)
          if LOG_2PC: print "sent",response
          return
         ####################
         #### MERGE_REQ #####
         ####################
        elif msg["who"] == "MERGE_REQ":
          if LOG_2PC: print "IN MERGE_REQ after READY_PAXOSED",msg
          response = {"parent":msg["parent"], "source": self.name, "type" : "READY", "key": "MERGE", "value": "MERGE_FWD"}
          if msg["tpcFROM"] == self.rgroup.leader:
            response["destination"] =  [self.lgroup.leader]
          elif msg["tpcFROM"] == self.lgroup.leader:
            response["destination"] =  [self.rgroup.leader]
          else:
            print "not leader of either group?"
            return
         ###################
         #### MERGE_FWD #####
         ###################
        elif msg["who"] == "MERGE_FWD":
          response = {"parent": msg["parent"] ,"destination": [msg["tpcFROM"]], "source": self.name, 
                      "type" : "YES", "key": "MERGE", "value": "MERGE_FWD"}


      self.SEND_MSG(response)
      if LOG_2PC: print "sent",response

    ###############
    ##### YES #####
    ###############   

    elif typ == "YES":
      if LOG_2PC: print "received yes",msg
      #type yes, key split,merge, val split,merge_id,merge_req,merge_fwd

       ####################
       #### MERGE_REQ #####
       ####################
      if msg["value"] == "MERGE_REQ":
        if LOG_2PC: print "IN MERGE_REQ IN YES"
        oldGroupMembers = [mem for mem in self.group.members]
        if msg["source"] == self.lgroup.leader:
          self.group = self.handle_merge("left")
          self.lgroup = msg["newNeighbor"]

          neighbor_id = self.rgroup.leader
          neighbor_fwd = msg["newNeighbor"]
          which = "leftMerge"

        elif msg["source"] == self.rgroup.leader:

          self.group = self.handle_merge("right")
          if LOG_2PC: print "survived merge"
          self.rgroup = dictToGroup(msg["newNeighbor"])
          neighbor_id = self.lgroup.leader
          neighbor_fwd = msg["newNeighbor"]
          which = "rightMerge"
        else:
          print "NOT LEADER OF GROUP??"
          neighbor = None
          return
        commit_msg = ({ "parent": msg["parent"] , "destination": [msg["source"]], 
                        "source": self.name, "type": "COMMIT", "key": "MERGE","value":"MERGE_REQ", 
                        "newGroup": (groupToDict(self.lgroup),groupToDict(self.group),groupToDict(self.rgroup)), "store": self.store})
        self.pending_reqs.append( ("commit", commit_msg["key"], commit_msg["value"], commit_msg["destination"][0]))
        self.SEND_MSG(commit_msg)
        if LOG_2PC: print "sent commit message to merger",commit_msg

        learn_msg = ({"parent": msg["parent"] ,"destination": oldGroupMembers, "source" : self.name, 
                      "type": "LEARN", "key": "GROUPS","p_num":self.group.p_num, 
                      "value": (groupToDict(self.lgroup),groupToDict(self.group),groupToDict(self.rgroup)), "store": msg["store"]})
        self.SEND_MSG(learn_msg)
        if LOG_2PC: print "sent learn merger to my own",learn_msg

        neighbor_msg = ({"parent": msg["parent"] , "destination": [neighbor_id], "source": self.name,"value":"MERGE_ID",
                         "type": "COMMIT", "key": "MERGE", "which": which, "newGroup": groupToDict(self.group)})
        self.pending_reqs.append( ("commit", neighbor_msg["key"], neighbor_msg["value"], neighbor_msg["destination"][0] ) )
        self.SEND_MSG(neighbor_msg)
        if LOG_2PC: print "sent commit merger neighbor",neighbor_msg

        other_leader = dictToGroup(neighbor_fwd).leader
        if LOG_2PC: print "\n\n",other_leader,"\n\n"
        neighbor2_msg = ({"parent": msg["parent"] , "source": self.name, "destination": [other_leader],"key":"MERGE", 
                          "type": "COMMIT", "value": "MERGE_FWD","which": which, "newGroup": groupToDict(self.group)})

        self.pending_reqs.append( ("commit", neighbor2_msg["key"], neighbor2_msg["value"], neighbor2_msg["destination"][0] ) )
        if LOG_2PC: print "sent commit merger neighbor",neighbor_msg
       #########################
       #### SPLIT,ADD,DROP #####
       #########################         
      elif msg["key"] == "SPLIT" or msg["key"] == "ADD" or msg["key"] == "DROP":
        if msg["key"] not in self.okays:
          if LOG_2PC: print "first yes"
          self.okays[ msg["key"] ] = 1
        else:
          if LOG_2PC: print "second yes!"
          del self.okays[ msg["key"] ]
          yes_paxos = ({"parent": msg["parent"], "source": self.name, "destination": [self.group.leader], 
                              "type": "PROPOSE", "key": "YES","value": msg["key"],"tpcFROM":msg["source"],
                               "who" : msg["value"],"p_num":self.group.p_num})
          self.SEND_MSG(yes_paxos)
          if LOG_2PC: print "sent yes to paxos",yes_paxos
          return
      else:
        self.SEND_MSG({"parent": msg["parent"], "source": self.name, "destination": [self.group.leader], 
                            "type": "PROPOSE", "key": "YES","tpcFROM":msg["source"],
                            "p_num":self.group.p_num,"value": msg["key"], "who" : msg["value"]})

     #######################
     ####  YES_PAXOSED  ####
     #######################
    elif typ == "YES_PAXOSED":
      if LOG_2PC: print "receieved YES_PAXOSED",msg
      # type yes_paxosed, key ready , value split,merge_id/add/drop, who split/merge_id/merge_req/merge_id/name/name
       ################
       #### SPLIT #####
       ################
      if msg["value"] == "SPLIT":
        if LOG_2PC: print "in split"
        group1, group2 = self.handle_split()
        g1 = groupToDict(group1)
        g2 = groupToDict(group2)

        groupTuple = (self.lgroup, group1 , group2)
        learn_msg1 = ({"parent": msg["parent"],
                       "destination": group1.members,
                       "source" : self.name, 
                       "type": "LEARN",
                       "key": "GROUPS",
                       "p_num":self.group.p_num,
                        "value": (groupToDict(self.lgroup),g1,g2),
                        "who":None,
                        "store":{}
                        })

        learn_msg2 = ({"parent": msg["parent"], "destination": group2.members, "source" : self.name, 
                       "type": "LEARN", "key": "GROUPS","p_num":self.group.p_num, "store": {},
                        "value": (g1, g2 , groupToDict(self.rgroup))})

        neighborL_msg = ({"parent": msg["parent"] , "destination": [self.lgroup.leader], "source": self.name,
                          "type": "COMMIT", "key": "SPLIT","which": "yourRight", "value": (g1)})
        self.pending_reqs.append( ("commit", neighborL_msg["key"], neighborL_msg["value"], neighborL_msg["destination"][0] ) )
        neighborR_msg = ({"parent": msg["parent"] , "destination": [self.rgroup.leader], "source": self.name,
                          "type": "COMMIT", "key": "SPLIT","which": "yourLeft", "value": (g2)})
        self.pending_reqs.append( ("commit", neighborR_msg["key"], neighborR_msg["value"], neighborR_msg["destination"][0] ) )

        self.SEND_MSG(learn_msg1)
        self.SEND_MSG(learn_msg2)
        self.SEND_MSG(neighborL_msg)
        self.SEND_MSG(neighborR_msg)
        if LOG_2PC: print "sent learnL"
        if LOG_2PC:  print "sent learnR"
        if LOG_2PC: print "sent COMMIT left",neighborL_msg
        if LOG_2PC: print "sent COMMIT right",neighborR_msg

        if BLOCKING:
          self.SEND_MSG({"parent":  msg["parent"] ,"destination": self.group.members, "source": self.name, 
                              "type": "LEARN", "key": "UNBLOCK","p_num":self.group.p_num})
          print "sent unblock"

        return
       ################
       #### ADD  ######
       ################
      elif msg["value"] == "ADD":


        newGroup = Group(self.group.key_range, self.group.leader, (self.group.members + [msg["who"]]), self.group.p_num)

        learn_msg = ({"parent": msg["parent"], "destination": newGroup.members, "source" : self.name, 
                      "type": "LEARN", "key": "ADD_SELF","p_num":self.group.p_num,
                       "value": (groupToDict(self.lgroup),groupToDict(newGroup),groupToDict(self.rgroup)), "store" : self.store})
        
        neighborL_msg = ({"parent": msg["parent"] , "destination": [self.lgroup.leader], "source": self.name,
                          "type": "COMMIT", "key": "ADD_OTHER","which": "yourRight", "value": msg["who"] })
        self.pending_reqs.append( ("commit", neighborL_msg["key"], neighborL_msg["value"], neighborL_msg["destination"][0] ) )

        neighborR_msg = ({"parent": msg["parent"] , "destination": [self.rgroup.leader], "source": self.name,
                          "type": "COMMIT", "key": "ADD_OTHER","which": "yourLeft", "value": msg["who"] })
        self.pending_reqs.append( ("commit", neighborR_msg["key"], neighborR_msg["value"], neighborR_msg["destination"][0] ) )

        self.SEND_MSG(learn_msg)
        self.SEND_MSG(neighborL_msg)
        self.SEND_MSG(neighborR_msg)

        if BLOCKING:
          self.SEND_MSG({"parent":  msg["parent"] ,"destination": self.group.members, "source": self.name, 
                            "type": "LEARN", "key": "UNBLOCK","p_num":self.group.p_num})
          print "sent unblock"

        ################
        ##### DROP #####
        ################
      elif msg["value"] == "DROP":
        learn_msg = ({"parent": msg["parent"], "destination": self.group.members, "source" : self.name, 
                      "type": "LEARN", "key": "DROP_SELF", "value": msg["who"],"p_num":self.group.p_num})

        neighborL_msg = ({"parent": msg["parent"] , "destination": [self.lgroup.leader], "source": self.name,
                          "type": "COMMIT", "key": "DROP_OTHER","which": "yourRight", "value": msg["who"]})
        self.pending_reqs.append(("commit", neighborL_msg["key"], neighborL_msg["value"], neighborL_msg["destination"][0]))

        neighborR_msg = ({"parent": msg["parent"] , "destination": [self.rgroup.leader], "source": self.name,
                                       "type": "COMMIT", "key": "DROP_OTHER","which": "yourLeft", "value": msg["who"] })
        self.pending_reqs.append( ("commit", neighborR_msg["key"], neighborR_msg["value"], neighborR_msg["destination"][0] ) )

        self.SEND_MSG(learn_msg)
        self.SEND_MSG(neighborL_msg)
        self.SEND_MSG(neighborR_msg)

        if BLOCKING:
          self.SEND_MSG({"parent":  msg["parent"] ,"destination": self.group.members, "source": self.name, 
                              "type": "LEARN", "key": "UNBLOCK","p_num":self.group.p_num})
          print "sent unblock"

         ################
         #### MERGE #####
         ################
      elif msg["value"] == "ELECTION":
        learn_msg = ({"parent": msg["parent"], "destination": self.group.members, "source" : self.name, 
                      "type": "LEARN", "key": "ELECTION", "value": msg["who"],"p_num":self.group.p_num})

        neighborL_msg = ({"parent": msg["parent"] , "destination": [self.lgroup.leader], "source": self.name,
                          "type": "COMMIT", "key": "ELECTION","which": "yourRight", "value": msg["who"]})
        self.pending_reqs.append(("commit", neighborL_msg["key"], neighborL_msg["value"], neighborL_msg["destination"][0]))

        neighborR_msg = ({"parent": msg["parent"] , "destination": [self.rgroup.leader], "source": self.name,
                                       "type": "COMMIT", "key": "ELECTION","which": "yourLeft", "value": msg["who"] })
        self.pending_reqs.append( ("commit", neighborR_msg["key"], neighborR_msg["value"], neighborR_msg["destination"][0] ) )

        self.SEND_MSG(learn_msg)
        self.SEND_MSG(neighborL_msg)
        self.SEND_MSG(neighborR_msg)
        if LOG_2PC: print "in election - yes_paxosed, sent",learn_msg,"\n",neighborL_msg,"\n",neighborR_msg        


      elif msg["value"] == "MERGE":
        if LOG_2PC:print "IN yes_paxosed MERGE",msg
        if msg["tpcFROM"] == self.lgroup.leader:
          dest = self.rgroup.leader
          groupInfo = self.lgroup
        elif msg["tpcFROM"] == self.rgroup.leader:
          dest = self.lgroup.leader
          groupInfo = self.rgroup
        else:
          print "ERROR LEADER NOT FOUND"
          return
         ###################
         #### MERGE_ID #####
         ###################
        if msg["who"] == "MERGE_ID":
          new_msg = {"parent": msg["parent"], "type": "READY", "destination": [dest], "source": self.name, 
                     "key": "MERGE", "value": "MERGE_REQ"}
          self.SEND_MSG(new_msg)
          if LOG_2PC: print "sent merge_req other way",new_msg
          ###################
          #### MERGE_FWD #####
          ###################
        elif msg["who"] == "MERGE_FWD":
          if LOG_2PC:print "IN MERGE_FWD ON YES_PAXOSED"
          new_msg = {"parent": msg["parent"], "type": "YES", "destination": [dest], "source": self.name,
                     "key": "MERGE", "value": "MERGE_REQ", "newNeighbor" : groupToDict(groupInfo), "store" : self.store}
          self.SEND_MSG(new_msg)
          if LOG_2PC:print "sent req yes to original",new_msg
          

                     #######################
                     ###### NO & WAIT ######
                     #######################
    elif typ == "NO" or typ == "WAIT":
      self.loop.add_timeout(time.time() + .5, 
                            lambda: self.SEND_MSG({"parent":msg["parent"], "type": "START", 
                                                        "destination":[self.group.leader], 
                                                        "source": self.name, "key": msg["key"], 
                                                        "value": msg["value"]}))
  ################
  #### COMMIT ####
  ################
    elif typ == "COMMIT":
      if LOG_2PC: print "\nRECIEVED COMMIT",msg

      comm_ack = ({"parent":  msg["parent"] ,"destination": [ msg["source"] ], "source": self.name, 
                          "type": "COMMIT_ACK", "req": ("commit", msg["key"], msg["value"], msg["destination"] )})
      self.SEND_MSG(comm_ack)

      if LOG_2PC: print "sent commit_ack",comm_ack

      if BLOCKING:
        self.SEND_MSG({"parent":  msg["parent"] ,"destination": self.group.members, "source": self.name, 
                            "type": "LEARN", "key": "UNBLOCK","p_num":self.group.p_num})
        print "sent unblock"

                     ################
                     #### SPLIT #####
                     ################
      if msg["key"] == "SPLIT":
        if msg["which"] == "yourRight":
          learn_msg = ({"parent": msg["parent"] ,"destination": self.group.members,
                         "source": self.name, "type": "LEARN", "p_num":self.group.p_num,"key": "GROUPS",
                         "value": (groupToDict(self.lgroup), groupToDict(self.group), msg["value"]), "store": dict()})
          if LOG_2PC: print "\nLEARN MSG\n",learn_msg,"\n\n"
        elif msg["which"] == "yourLeft":
          learn_msg = ({"parent" : msg["parent"] ,"destination": self.group.members,
                         "source" : self.name, "type": "LEARN","p_num":self.group.p_num, "key": "GROUPS",
                        "value": (msg["value"], groupToDict(self.group) , groupToDict(self.rgroup)), "store" : dict()})
        else:
          print "SPLIT COMMIT ILLFORMED - which is messed"
        self.SEND_MSG(learn_msg)
        if LOG_2PC: print "SENT LEARN",learn_msg,"\n"
        return
                     ################
                     #### MERGE #####
                     ################
      elif msg["key"] == "MERGE":

                     ###################
                     #### MERGE_ID #####
                     ###################
        if msg["value"] == "MERGE_ID":
          if LOG_2PC: print "in Merge ID Commit response",msg["which"]
          ngroup = dictToGroup(msg["newGroup"])
          lBound1,rBound1 = int(ngroup.key_range[0]),int(ngroup.key_range[1])
          lBound2,rBound2 = int(self.group.key_range[0]),int(self.group.key_range[1])

          if (rBound1 == lBound2 and  lBound1 == rBound2) or \
             (lBound1 == MIN_KEY and rBound1 == lBound2 and rBound2 == MAX_KEY) or \
             (rBound1 == MAX_KEY and lBound1 == rBound2 and lBound2 == MIN_KEY):
            if LOG_2PC: print "ONLY TWO GROUPS"
            learn_msg = ({ "destination": self.group.members, "source" : self.name,
                           "type": "LEARN","p_num":self.group.p_num,
                           "key": "GROUPS", "value": (msg["newGroup"],groupToDict(self.group),msg["newGroup"]), "store": dict()})
          elif msg["which"] == "leftMerge":
            learn_msg = ({ "destination": self.group.members, "source" : self.name,
                           "type": "LEARN","p_num":self.group.p_num,
                           "key": "GROUPS", "value": (msg["newGroup"],groupToDict(self.group),groupToDict(self.rgroup)), "store": dict()})
          elif msg["which"] == "rightMerge":
            if LOG_2PC: print "rightMerge"
            learn_msg = ({ "parent" : msg["parent"] ,"destination": self.group.members,
                           "source" : self.name, "type": "LEARN","p_num":self.group.p_num,
                           "key": "GROUPS", "value": (groupToDict(self.lgroup), groupToDict(self.group), msg["newGroup"]),
                           "store": dict()})
          else:
            print "Commit illformed w/o which field"
          self.SEND_MSG(learn_msg)
          if LOG_2PC: print "SENT LEARN",learn_msg    
                     ####################
                     #### MERGE_REQ #####
                     ####################
        elif msg["value"] == "MERGE_REQ":
          if LOG_2PC: print "IN MERGE REQ"
          print "\n\nSTORE??",msg,"\n\n"
          learn_msg = ({"parent" : msg["parent"] ,"destination": self.group.members,
                         "source" : self.name, "type": "LEARN", "p_num":self.group.p_num,
                        "key": "GROUPS", "value": (msg["newGroup"]), "store" : msg["store"]})
          self.SEND_MSG(learn_msg)  
          if LOG_2PC: print "SENT LEARN",learn_msg     
                     ####################
                     #### MERGE_FWD #####
                     ####################
        elif msg["value"] == "MERGE_FWD":
          lBound1,rBound1 = int(ngroup.key_range[0]),int(ngroup.key_range[1])
          lBound2,rBound2 = int(self.group.key_range[0]),int(self.group.key_range[1])

          if (rBound1 == lBound2 and  lBound1 == rBound2) or \
             (lBound1 == MIN_KEY and rBound1 == lBound2 and rBound2 == MAX_KEY) or \
             (rBound1 == MAX_KEY and lBound1 == rBound2 and lBound2 == MIN_KEY):
            if LOG_2PC: print "ONLY TWO GROUPS"
            learn_msg = ({ "destination": self.group.members, "source" : self.name,
                           "type": "LEARN","p_num":self.group.p_num,
                           "key": "GROUPS", "value": (msg["newGroup"],groupToDict(self.group),msg["newGroup"]), "store": dict()})
          elif msg["which"] == "rightMerge":
            learn_msg = ({"parent" : msg["parent"] ,"destination": self.group.members,
                         "source" : self.name, "type": "LEARN", "p_num":self.group.p_num,
                          "key": "GROUPS", "value": (msg["value"],self.group,self.rgroup), "store": dict()})
          elif msg["which"] == "leftMerge":
            learn_msg = {"parent" : msg["parent"] ,"destination": self.group.members, "source" : self.name, 
                            "type": "LEARN", "key": "GROUPS","p_num":self.group.p_num,
                             "value": (self.lgroup, self.group, msg["value"]), "store": dict()}
          else:
            print "Commit illformed w/o which field"
          self.SEND_MSG(learn_msg)
          if LOG_2PC: print "SENT LEARN",learn_msg
                     #########################
                     #### ADD/DROP_OTHER #####
                     #########################
      elif msg["key"] == "ADD_OTHER" or msg["key"] == "DROP_OTHER":

          learn_msg = ({  "parent" : msg["parent"] ,"destination": self.group.members, "source" : self.name, 
                          "type": "LEARN", "key": msg["key"],"p_num":self.group.p_num,
                           "value": (msg["value"]), "which" : msg["which"] })
          self.SEND_MSG(learn_msg)
          if LOG_2PC: print "sent learn add_other",learn_msg

      elif msg["key"] == "ELECTION":
          learn_msg = {"type":"LEARN","key":"ELECTION","parent":msg["parent"],"destination":self.group.members,
                            "source":self.name,"p_num":self.group.p_num, "value":msg["value"],"which":msg["which"]}               
          self.SEND_MSG(learn_msg)
          if LOG_2PC: print "SENT LEARN",learn_msg
      else:
          raise Exception("This isnt a valid Commit type={}".format(typ))
    else:
        raise Exception("wow how did that happen")
  '''
  def shouldBlock(self,msg):
    print "in shouldBlock"
    if self.BLOCK_2PC == None or msg["type"] in TWOPC_UNBLOCKED:
      return False
    if self.BLOCK_2PC[0] == (msg["parent"]):
      if self.BLOCK_2PC[0] == "MERGE":
        if msg["key"] in ["MERGE","MERGE_REQ","MERGE_FWD","MERGE_ID"]:
          return False
    return True 
  '''
  def send_spam(self):
    '''
    Periodically send spam, with a counter to see which are dropped.
    '''
    if not hasattr(self, 'spam_count'):
      self.spam_count = 0
      self.spam_count += 1
      t = self.loop.time()
      self.SEND_MSG({'type': 'spam', 'id': self.spam_count, 'timestamp': t, 
                          'source': self.name, 'destination': self.peer_names, 'value': 42})
      self.loop.add_timeout(t + 1, self.send_spam)

  def shutdown(self, sig, frame):
        self.loop.stop()
        self.sub_sock.close()
        self.req_sock.close()
        sys.exit(0)

def groupToDict(g):
  return  {"key_range":g.key_range,
          "leader":g.leader,
          "leaderLease":str(g.leaderLease),
          "members":g.members,
          "p_num":g.p_num
          }

def dictToGroup(g):

  #self.group = Group((key_range[0], key_range[1]), peer_names[0], peer_names, 1)  #group object  
  return Group(
              (long(g["key_range"][0]),
              long(g["key_range"][1])),
              g["leader"],
              g["members"],
              int(g["p_num"])
              )


def make_paxos_msg(typ, dst, src, key, value, p_num, prior_proposal, parent, who, tpcFROM):
  if dst == None: print "\n\nMASSIVE ERROR - NO DST\n\n"
  return {"type": typ, "destination": dst, "source": src, "key": key, "value": value, 
          "p_num": p_num, "prior_proposal": prior_proposal, "parent": parent, "who": who, "tpcFROM":tpcFROM}

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

  parser.add_argument('--key-range', dest='key_range',
                      type=str, default='')

  parser.add_argument('--pred-group', dest='pred_group', 
                      type=str, default='')
  parser.add_argument('--key-range1', dest='key_range1',
                      type=str, default='')
  parser.add_argument('--succ-group', dest="succ_group",
                      type=str, default='')
  parser.add_argument('--key-range2', dest='key_range2',
                      type=str, default='')
  args = parser.parse_args()

  args.peer_names = args.peer_names.split(',')
  args.key_range = args.key_range.split(',')
  args.key_range1 = args.key_range1.split(',')
  args.key_range2 = args.key_range2.split(',')
  args.pred_group = args.pred_group.split(',')
  args.succ_group = args.succ_group.split(',')
 
  Node(args.node_name, args.pub_endpoint, args.router_endpoint, args.spammer,
       args.peer_names, args.key_range, args.pred_group, args.key_range1, 
       args.succ_group, args.key_range2).start()
