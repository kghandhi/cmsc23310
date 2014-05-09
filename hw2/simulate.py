class Proposer(object):
    def __init__(self, ID, ...):
        self.ID = ID
        self.failed = False

class Acceptor(object):
    def __init__(self, ID, ...):
        self.ID
        self.failed = False

class Message(object):
    def __init__(self, value, typ, src, dst):
        self.value = value #thing
        self.typ = typ #string
        self.src = src #list
        self.dst = dst #possibly will be like p_1 should change somehow

def simulate(n_p, n_a, t, E):
    props = []
    accs = []
    for i in xrange(n_p):
        props.append(Proposer(i+1, ...))

    for j in xrange(n_a):
        accs.append(Acceptor(j+1, ...))

    N = [] #empty network? should it be a se?

    for i in xrange(t):
        if (len(N) == 0) and (len(E) == 0):
            return
        for event in E:
            if event[0] = t:
                e = event
        if len(e) != 0:
            E.remove(e)
            for c in e[1]: #F failed computers
                c.failed = True #figure this out, should p_1 or a_1 refer to the object?
            for c in e[2]: #R revived computers
                c.failed = False
            if (len(e[3]) != 0) and (len(e[4]) != 0): #pi_c = proposer, pi_v = value proposed
                m = Message(e[4][0], "PROPOSE", [], e[3][0])
                Deliver_Message(e[3][0], m)
            else:
                m = Extract_Message(N)
                if len(m) != 0: #resolve!
                    Deliver_Message(m.dst, m)
        else:
            m = Extract_Message(N):
            if len(m) != 0: #resolve!
                Deliver_Message(m.dst,m)
               
             
                
