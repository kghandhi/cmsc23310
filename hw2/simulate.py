from sys import argv
import logging
import paxos
import fileinput

class Event(paxos.EqualityMixin):
    def __init__(self, t, F, R, pi_c, pi_v):
        self.t = t
        self.F = F #dictionary of computers who fail       
        self.R = R #dictionary of computers who recover         
        self.pi_c = pi_c #proposer ID proposing something    these are lists
        self.pi_v = pi_v #value proposer proposes. both this and pi_v should be null if either is

    def __repr__(self):
        FMT = "Event(t={}, F={}, R={}, pi_c={}, pi_v={})"
        return FMT.format(self.t, self.F, self.R, self.pi_c, self.pi_v)
    
def simulate(n_p, n_a, t_max, E):
    props = [] #static list of proposers (access proposer i by doing props[i-1]
    accs = [] #static list of acceptors (access acceptor i by doing accs[i-1]
    
    for j in xrange(n_a):
        accs.append(paxos.Acceptor(j+1))
    for i in xrange(n_p):
        props.append(paxos.Proposer(i+1, accs))

    N = [] #empty network? should it be a set? this is a queue of messages, will change

    for i in xrange(t_max):
        to_print = "%d: " %i
        if (len(N) == 0) and (len(E) == 0):
            for proposer in props:
                if len(proposer.props_accepted):
                    for key in proposer.props_accepted:
                        tup = proposer.props_accepted[key] 
                        print "P%d has reached consensus (proposed %d, accepted %d)" %(proposer.ID, tup[0], tup[1])
            return
        if i in E:
            e = E[i]
        else:
            e = 0
        if e != 0:
            del E[i]
            for p_id in e.F['P']:
                props[p_id - 1].failed = True
                to_print += "** P %d FAILS **" %p_id
            for a_id in e.F['A']:
                accs[a_id - 1].failed = True
                to_print += ("** A %d FAILS **" %a_id)
            for p_id in e.R['P']:
                props[p_id - 1].failed = False
                to_print += "** P %d RECOVERS **" %p_id
            for a_id in e.R['A']:
                accs[a_id - 1].failed = False 
                to_print += "%d ** A %d RECOVERS **" %(i, a_id)
           
            if (len(e.pi_c) != 0) and (len(e.pi_v) != 0): #pi_c = proposer, pi_v = value proposed
                msg = paxos.Message(e.pi_v[0], "PROPOSE", [], ('P',e.pi_c[0]), paxos.proposal_id, [])
                props[e.pi_c[0] - 1].deliver_message(N, msg)
                to_print += msg.print_msg()
            else:
                msg = paxos.extract_message(N, accs, props)
                if msg != 0: #resolve!
                    if msg.dst[0] == 'A':
                        c = accs[msg.dst[1]-1]
                    else:
                        c = props[msg.dst[1]-1]
                    c.deliver_message(N, msg) #who do i deliver message to???
                    to_print += msg.print_msg()
                    
        else:
            msg = paxos.extract_message(N, accs, props)
            if msg != 0: #resolve!
                if msg.dst[0] == 'A':
                    c = accs[msg.dst[1]-1]
                else:
                    c = props[msg.dst[1]-1]
                c.deliver_message(N, msg)
                to_print += msg.print_msg()
        print to_print
    
             
def main(n_p, n_a, t_max, E):
    print "(n_p=%d, n_a=%d, t_max=%d,E)" %(n_p, n_a, t_max)
    print E
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
                
           
                

           
