
class Event(object):
    def __init__(self, t, F, R, pi_c, pi_v):
        self.t = t
        self.F = F #dictionary of computers who fail       
        self.R = R #dictionary of computers who recover         
        self.pi_c = pi_c #proposer ID proposing something    these are lists
        self.pi_v = pi_v #value proposer proposes. both this and pi_v should be null if either is

def simulate(n_p, n_a, t_max, E):
    props = [] #static list of proposers (access proposer i by doing props[i-1]
    accs = [] #static list of acceptors (access acceptor i by doing accs[i-1]
    
    for j in xrange(n_a):
        accs.append(Acceptor(j+1, ...))
    for i in xrange(n_p):
        props.append(Proposer(i+1, accs))

    N = [] #empty network? should it be a set? this is a queue of messages, will change

    for i in xrange(t_max):
        if (len(N) == 0) and (len(E) == 0):
            return
        for event in E:
            if event.t == i:
                e = event
        if len(e) != 0:
            E.remove(e)
            # for c in e.F: #F failed computers
            #     c.failed = True #figure this out, should p_1 or a_1 refer to the object?
            #  for c in e.R: #R revived computers
            #     c.failed = False
            for p_id in e.F['P']:
                props[p_id - 1].failed = True
            for a_id in e.F['A']:
                accs[a_id - 1].failed = True
            for p_id in e.R['P']:
                props[p_id - 1].failed = False
            for a_id in e.R['A']:
                accs[a_id - 1].failed = False 
           
            if (len(e.pi_c) != 0) and (len(e.pi_v) != 0): #pi_c = proposer, pi_v = value proposed
                msg = Message(e.pi_v[0], "PROPOSE", [], e.pi_c[0])
                Deliver_Message(e.pi_c[0], msg)
            else:
                msg = Extract_Message(N)
                if msg != 0: #resolve!
                    Deliver_Message(msg.dst, msg)
        else:
            msg = Extract_Message(N):
            if msg != 0: #resolve!
                Deliver_Message(msg.dst, msg)
               
             
def main(n_p, n_a, t_max, E):
    simulate(n_p, n_a, t_max, E)
    
if __name__ == '__main__':
    E = []
    t_max = int(t_max_s)
    ev_dic = {}
    #i think id need to reverse these loops
        
        for l in fileinput.input():
            line = l.strip('\n').split(" ")
            if (len(line) == 2) and (line[1] == "END"): 
                #order ev_dic by key then put in E
                break
            if (len(line) == 3):
                n_p, n_a, t_max_s = line
            elif (len(line) == 4):
                if line[0] in ev_dic:
                    e = ev_dic[line[0]] 
                    if line[1] == "FAIL":
                        e.F[line[2][0]].append(line[3])
                    elif line[1] == "RECOVER":
                        e.R[line[2][0]].append(line[3])
                    elif line[1] == "PROPOSE":
                        e.pi_c.append(line[2])
                        e.pi_v.append(line[3])
                    else: 
                        print "INVALID INPUT"
                else:
                    F = {'P': [], 'A': []}
                    R = {'P': [], 'A': []}
                    pi_c = []
                    pi_v = []
                    if line[1] == "FAIL":
                        F[line[2][0]].append(line[3])
                    elif line[1] == "RECOVER":
                        R[line[2][0]].append(line[3])
                    elif line[1] == "PROPOSE":
                        pi_c.append(line[2])
                        pi_v.append(line[3])
                    else: 
                        print "INVALID INPUT"
                    ev_dic[line[0]] = Event(line[0], F, R, pi_c, pi_v)
                    
    main(int(n_p), int(n_a), t_max, E)
                
           
                

           
