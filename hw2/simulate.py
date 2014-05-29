from sys import argv
import paxos
import fileinput

class Event(paxos.EqualityMixin):
    def __init__(self, t, F, R, pi_c, pi_v):
        self.t = t
        self.F = F #dictionary of computers who fail       
        self.R = R #dictionary of computers who recover         
        self.pi_c = pi_c #proposer ID proposing. either [] or [pi_c]
        self.pi_v = pi_v #value to propose. either [] or [pi_v]

    def __repr__(self):
        fmt = "Event(t={}, F={}, R={}, pi_c={}, pi_v={})"
        return fmt.format(self.t, self.F, self.R, self.pi_c, self.pi_v)

def results(props):
    print 
    print 
    for proposer in props:
        if len(proposer.props_accepted):
            for key in proposer.props_accepted:
                tup = proposer.props_accepted[key] 
                print "P{} has reached consensus (proposed {}, accepted {})" \
                .format(proposer.ID, tup[0], tup[1])
        else:
            print "P{} did not reach consensus".format(proposer.ID)
    
def simulate(n_p, n_a, t_max, E):
    props = [] #static list of proposers (access proposer i by doing props[i-1]
    accs = [] #static list of acceptors (access acceptor i by doing accs[i-1]
    
    for j in xrange(n_a):
        accs.append(paxos.Acceptor(j+1))
    for i in xrange(n_p):
        props.append(paxos.Proposer(i+1, accs))

    N = [] #empty network

    for i in xrange(t_max+1):
        print_dummy = False #sorry
        to_print = "%d: " %i

        if (len(N) == 0) and (len(E) == 0):
            results(props)
            return
        if i in E:
            e = E[i]
        else:
            e = 0
        if e != 0:
            del E[i]
            for p_id in e.F['P']:
                props[p_id - 1].failed = True
                print_dummy = True
                print to_print + "** P{} FAILS **".format(p_id)
            for a_id in e.F['A']:
                accs[a_id - 1].failed = True
                print_dummy = True
                print to_print + "** A{} FAILS **".format(a_id)
            for p_id in e.R['P']:
                props[p_id - 1].failed = False
                print_dummy = True
                print to_print + "** P{} RECOVERS **".format(p_id)
            for a_id in e.R['A']:
                accs[a_id - 1].failed = False 
                print_dummy = True
                print to_print + "** A{} RECOVERS **".format(a_id)
               
            if (len(e.pi_c) != 0) and (len(e.pi_v) != 0): 
                msg = paxos.Message(e.pi_v[0], "PROPOSE", [], \
                                    ('P', e.pi_c[0]), paxos.proposal_id, None)
                props[e.pi_c[0] - 1].deliver_message(N, msg)
                print_dummy = True
                print to_print + msg.print_msg()
            else:
                msg = paxos.extract_message(N, accs, props)
                if msg != 0: 
                    if msg.dst[0] == 'A':
                        c = accs[msg.dst[1]-1]
                    else:
                        c = props[msg.dst[1]-1]
                    c.deliver_message(N, msg) 
                    print_dummy = True
                    print to_print + msg.print_msg()
                    
        else:
            msg = paxos.extract_message(N, accs, props)
            if msg != 0: 
                if msg.dst[0] == 'A':
                    c = accs[msg.dst[1]-1]
                else:
                    c = props[msg.dst[1]-1]
                c.deliver_message(N, msg)
                print_dummy = True
                print to_print + msg.print_msg()
        if not print_dummy:
            print to_print
    results(props)
    return
    
             
def main(n_p, n_a, t_max, E):
    simulate(n_p, n_a, t_max, E)

#the complication of reading in a file. It will not work always with comments
#at the top! But it will work if the comments arent 2,3,or4 strings
def proc_input(file_handle):    
    E = {}
    for l in file_handle:
        line = l.strip('\n').split(" ")
        if (len(line) == 2) and (line[1] == "END"): 
            break
        if len(line) == 3:
            n_p, n_a, t_max_s = line
        elif len(line) == 4:
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
                
           
                

           
