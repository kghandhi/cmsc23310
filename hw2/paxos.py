from __future__ import division

proposal_id = 1

class EqualityMixin(object):
    def __eq__(self, other):
        for key, value in self.__dict__.items():
            if other.__dict__[key] != value:
                return False
        return True


class Message(EqualityMixin):
    def __init__(self, value, typ, src, dst, n, prior_proposal):
        self.value = value #thing
        self.typ = typ #string PROPOSE, PREPARE, PROMISE, ACCEPT, ACCEPTED, REJECTED
        self.src = src #list, make sure this isnt a list and can reference an actual computer
        self.dst = dst #possibly will be like p_1 should change somehow
        self.n = n #if not a proposal should this ID be negative?
        self.prior_proposal = prior_proposal #list containing nothing or a value and p_id

    def __repr__(self):
        FMT = "Message(value={}, typ={}, src={}, dst={}, n={}, prior_proposal={})"
        
        return FMT.format(self.value, self.typ, self.src, self.dst, 
                          self.n, self.prior_proposal)


#Adds message m to the end of the queue.
def queue_message(N, m):
    N.append(m)

#finds the first message m in the queue st m.src.failed 
def extract_message(N): 
    for message in N:
        if (message.src.failed == False) and (message.dst.failed == False):
            msg = message
            N.remove(msg)
            return msg
        else:
            return 0 #consider creating a length of message function 
           
class Proposer(object):
    def __init__(self, ID, accs):
        self.ID = ID
        self.failed = False
        self.accs = accs #list of acceptors
        self.promises = {} #keys are proposal_id, items are lists of promises for that id.
        self.rejects = {}
        self.majority = len(self.accs) / 2
        self.accepts = {}

    #should take arguments c and msg.     
    def deliver_message(self, N, msg):
        if msg.typ == "PROPOSE":
            for c_a in self.accs:
                new_msg = Message(msg.pi_v, "PREPARE", self.ID, c_a.ID, proposal_id, [])
                queue_message(N, new_msg)
            proposal_id += 1 #this could be very very wrong
        
        elif msg.typ == "PROMISE":
            if msg.n > msg.prior_proposal[1]:
                self.promises[msg.n].append((msg.value, msg.n))
            else:
                self.promises[msg.n].append(msg.prior_proposal)
            if (len(self.promises[msg.n]) > self.majority):
                pick_tup = sorted(self.promises[msg.n], key=lambda x: x[1])[0]
                for c_a in self.accs:
                    new_msg = Message(pick_tup[0], "ACCEPT", self.ID, c_a.ID, pick_tup[1], [])
                    queue_message(N, new_msg)
        
        elif msg.typ == "REJECTED":
            self.rejects[msg.n].append((msg.value, msg.n))
            if (len(self.rejects[msg.n]) > self.majority):
                for c_a in self.accs:
                    new_msg = Message(msg.pi_v, "PREPARE", self.ID, c_a.ID, proposal_id, [])
                    queue_message(N, new_msg)
                proposal_id +=1
        
        elif msg.typ == "ACCEPTED":
            if (len(self.accepts[msg.n]) > self.majority):
                print "PROTOCOL TERMINATED"
                self.accepts[msg.n].append((msg.value, msg.n))
            # else: I FEEL LIKE THIS SHOULDNT BE A THING
            #     for c_a in self.accs:
            #         new_msg = Message(msg.pi_v, "PREPARE", self.ID, c_a.ID, proposal_id, [])
            #         queue_message(N, new_msg)
            #     proposal_id +=1
        else:
            print "This is not a type of message a Proposer should be receiving"
            

class Acceptor(object):
    def __init__(self, ID):
        self.ID = ID
        self.failed = False
        self.n_int = 0 #initialize the highest prepare request it has responded to?
        self.accs = []

    def deliver_message(self, N, msg):
        if msg.typ == "PREPARE":
            if msg.n > self.n_int:
                self.n_int = msg.n
                # if len(self.acc_ls): 
                #     tups = [(x.value, x.n) for x in self.acc_ls]
                #     high_p = sorted(tups, key=lambda x: x[1])[0]
                # else:
                #     high_p = []
                new_msg = Message(msg.value, "PROMISE", self.ID, msg.src, msg.n, self.accs)
            else:
                new_msg = Message(msg.value, "REJECTED", self.ID, msg.src, msg.n, [])
            queue_message(N, new_msg)

        elif msg.typ == "ACCEPT":
            if n_int < msg.n:
                new_msg = Message(msg.value, "ACCEPTED", self.ID, msg.src, msg.n, [])
                self.accs.append(msg.value, msg.n)
            else:
                new_msg = Message(msg.value, "REJECTED", self.ID, msg.src, msg.n, [])
            queue_message(N, new_msg)
        else:
            print "This is not a type of message an Acceptor should be receiving"

