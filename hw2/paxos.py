proposal_id = 0

class Message(object):
    def __init__(self, value, typ, src, dst, n):
        self.value = value #thing
        self.typ = typ #string PROPOSE, PREPARE, PROMISE, ACCEPT, ACCEPTED, REJECTED
        self.src = src #list, make sure this isnt a list and can reference an actual computer
        self.dst = dst #possibly will be like p_1 should change somehow
        self.n = n #if not a proposal should this ID be negative?

def Queue_Message(N, m):
    N.append(m)

#possibly also should be part of a computer 
def Extract_Message(N): 
#finds the first message m in the queue st m.src.failed 
    for message in N:
        if (message.src.failed = False) and (message.dst.failed = False):
            msg = message
            N.remove(msg)
            return msg
        else:
            return 0 #consider creating a length of message function 

#should be in the definition of the acceptor or the proposer, 
#but maybe not because it takes a computer            
class Proposer(object):
    def __init__(self, ID, accs,...):
        self.ID = ID
        self.failed = False
        self.accs = accs #list of acceptors
    def Deliver_Message(self, N, c, msg):
        if msg.typ == "PROPOSE":
            proposal_id += 1
            for c_a in self.accs:
                Queue_Message(N, Message(msg.pi_v, "PREPARE", self.ID, c_a.ID, proposal_id))
        if msg.typ == 

class Acceptor(object):
    def __init__(self, ID, ...):
        self.ID
        self.failed = False


