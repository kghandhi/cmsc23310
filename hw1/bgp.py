from sys import argv
import logging

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger(__name__)

#HELPER FUNCTIONS
def order_to_int(order):
    if order == "ATTACK" or order == 'A':
        return 1
    elif order == "RETREAT" or order == 'R':
        return -1
    else:
        return 0

def int_to_order(num):
    if num == 1:
        return "A"
    elif num == -1:
        return "R"
    else:
        return "-"

def loy_to_bool(loy):
    return loy == 'L'

def flip(order):
    return -order

def majority_s(orders):
    det = sum(orders)
    if det == 0:
        return '-'
    elif det > 0:
        return 'A'
    else:
        return 'R'

def majority(orders):
    det = sum(orders)
    if det == 0:
        return 'TIE'
    elif det > 0:
        return 'ATTACK'
    else:
        return 'RETREAT'

def condense(orders, m): #orders is a list of messages
    if m == 1:
        return orders

    longest = [msg for msg in orders if len(msg[0]) == m + 1]
    new_orders = [msg for msg in orders if len(msg[0]) != m + 1]

    while longest:
        to_match = longest[0][0][:-1]

        matches = [msg for msg in longest if msg[0][:-1] == to_match]
        longest = [msg for msg in longest if msg[0][:-1] != to_match]
        
        orders = [msg[1] for msg in matches]
        maj = order_to_int(majority_s(orders))
        
        new_orders.append((to_match, maj))

    return condense(new_orders, m - 1) 

# class Msg(object):
#     def __init__(self, sender, order):
#         self.sender = sender
#         self.order = order

#     def add_sender(self, new):
#         new_sender = [x for x in self.sender]
#         new_sender.append(new)
#         return new_sender
    
#     def last(self):
#         return self.sender[-1]
    
class General(object):
    def __init__(self, m, loyalty, order, ID):
        self.m = m
        self.orders = []#[([0], order)]
        self.ID = ID
        self.loyalty = loy_to_bool(loyalty)
        self.order = order
    
        
    def receive(self, ls, sender, order, m):
        LOG.debug("SENDER = {}, TARGET = {}, order = {}, m ={}".format(sender, self.ID, order, m))
        if m > 0:
            new_sender = [x for x in sender]
            if sender[-1] != self.ID:
                new_sender.append(self.ID)
            self.orders.append((new_sender, order))
            
            for m in xrange(m):
                self.relay(ls, new_sender, order, m) 
        else:
            self.orders.append((sender,order))
        return
        
    def relay(self, ls, sender, order, m):
        for i in xrange(len(ls)):
            if (ls[i] != self) and (sender[-1] != ls[i].ID):
                if self.loyalty:
                    ls[i].receive(ls, sender, order, m)
                elif (ls[i].ID % 2):
                    ls[i].receive(ls, sender, flip(order), m)
                else:
                    ls[i].receive(ls, sender, order, m)

# def run(m, ls):
#     for _ in xrange(m-1, -1, -1):
#         for l in ls:
#             for msg in l.orders:
#                 l.receive(ls, msg[0], msg[1], m)
                
                #l.relay(ls, msg[0].append(l.ID), msg[1], m)
    
def run(m, ls):
    for _ in xrange(m, -1, -1):
        for l in ls:  
            l.receive(ls, [0], l.order, m)
            
                
    return ls

def complete(m, ls):
    for i in xrange(len(ls)):
        condensed = condense(ls[i].orders, m)
        print condensed
        msgs = sorted(condensed, key=lambda x: x[0][1])
        i_decisions = [msg[1] for msg in msgs]
        decisions = [int_to_order(dc) for dc in i_decisions]
        print decisions
        print decisions[i] + ' ' + ''.join(decisions[:i]) + ' ' + ''.join(decisions[i+1:]) + ' ' + majority(i_decisions)
    print
    return
        
def spawn(L_loyalties, loyalty, m, order):
    ret = []
    for i in xrange(len(L_loyalties)):
        if loyalty == 'L':
            ret.append(General(m, L_loyalties[i], order_to_int(order), i+1))
        elif ((i % 2) == 0):
            ret.append(General(m, L_loyalties[i], 1, i+1))
        else:
            ret.append(General(m, L_loyalties[i], -1, i+1))
    return ret

def main(m, loyalties, order):
    i_order = order_to_int(order)
    loy = loy_to_bool(loyalties[0])
    
    ls = spawn(loyalties[1:], loy, m, i_order)
    print len(ls)

    run(m, ls)   
    complete(m, ls)
    
if __name__ == '__main__':
    for line in open(argv[1]):
        str_m, str_loyalties, _order = line.strip('\n').split(" ")
        if((str_loyalties == _order) and _order == "END"):
            pass
        else:
            _m = int(str_m)
            _loyalties = list(str_loyalties)
            main(_m, _loyalties, _order[0])
