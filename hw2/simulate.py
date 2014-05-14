from sys import argv
import logging
import paxos
import fileinput

class Event(object):
    def __init__(self, t, F, R, pi_c, pi_v):
        self.t = t
        self.F = F #dictionary of computers who fail       
        self.R = R #dictionary of computers who recover         
        self.pi_c = pi_c #proposer ID proposing something    these are lists
        self.pi_v = pi_v #value proposer proposes. both this and pi_v should be null if either is

    def __eq__(self, other):
        for key, value in self.__dict__.items():
            if other.__dict__[key] != value:
                return False
        return True


    def __repr__(self):
        FMT = "Event(t={}, F={}, R={}, pi_c={}, pi_v={})"
        return FMT.format(self.t, self.F, self.R, self.pi_c, self.pi_v)

def simulate(n_p, n_a, t_max, E):
    props = [] #static list of proposers (access proposer i by doing props[i-1]
    accs = [] #static list of acceptors (access acceptor i by doing accs[i-1]
    
    for j in xrange(n_a):
        accs.append(Acceptor(j+1))
    for i in xrange(n_p):
        props.append(Proposer(i+1, accs))

    N = [] #empty network? should it be a set? this is a queue of messages, will change

    for i in xrange(t_max):
        if (len(N) == 0) and (len(E) == 0):
            return
        if i in E:
            e = E[i]
        else:
            e = 0
        if e != 0:
            del E[i]
            for p_id in e.F['P']:
                props[p_id - 1].failed = True
            for a_id in e.F['A']:
                accs[a_id - 1].failed = True
            for p_id in e.R['P']:
                props[p_id - 1].failed = False
            for a_id in e.R['A']:
                accs[a_id - 1].failed = False 
           
            if (len(e.pi_c) != 0) and (len(e.pi_v) != 0): #pi_c = proposer, pi_v = value proposed
                msg = Message(e.pi_v[0], "PROPOSE", [], e.pi_c[0], proposal_id, [])
                props[e.pi_c - 1].deliver_message(e.pi_c[0], msg)
            else:
                msg = extract_message(N)
                if msg != 0: #resolve!
                    deliver_message(msg.dst, msg) #who do i deliver message to???
        else:
            msg = extract_message(N)
            if msg != 0: #resolve!
                deliver_message(msg.dst, msg)
               
             
def main(n_p, n_a, t_max, E):
    simulate(n_p, n_a, t_max, E)

def proc_input(file_handle):    
    E = {}
    for l in file_handle:
        line = l.strip('\n').split(" ")
        if (len(line) == 2) and (line[1] == "END"): 
           break
        if (len(line) == 3):
            n_p, n_a, t_max_s = line
        elif (len(line) == 4):
            key = int(line[0])
            
            if key in E:
                e = E[key]
                if line[1] == "FAIL":
                    e.F[line[2][0]].append(int(line[3]))
                elif line[1] == "RECOVER":
                    e.R[line[2][0]].append(int(line[3]))
                elif line[1] == "PROPOSE":
                    e.pi_c.append(int(line[2]))
                    e.pi_v.append(int(line[3]))
                else: 
                    print "INVALID INPUT"
            else:
                F = {'P': [], 'A': []}
                R = {'P': [], 'A': []}
                pi_c = []
                pi_v = []
                if line[1] == "FAIL":
                    F[line[2][0]].append(int(line[3]))
                elif line[1] == "RECOVER":
                    R[line[2][0]].append(int(line[3]))
                elif line[1] == "PROPOSE":
                    pi_c.append(int(line[2]))
                    pi_v.append(int(line[3]))
                else: 
                    print "INVALID INPUT"
                E[key] = Event(key, F, R, pi_c, pi_v)
    return int(n_p), int(n_a), int(t_max_s), E


if __name__ == '__main__':
    n_p, n_a, t_max_s, E = proc_input(fileinput.input())
                    
    main(n_p, n_a, t_max_s, E)
                
           
                

           
