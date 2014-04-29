from sys import argv
import logging

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger(__name__)

def switch(order):
    if order == 'A':
        return 'R'
    else:
        return 'A'

class General(object):
    def __init__(self, m, loyalty, order, ID):
        self.m = m   
        self.loyalty = loyalty
        self.orders = [] #[([0, ID], order[0])]
        self.ID = ID
        self.order = order

    def receive(self, sender, order, ls, m):
        LOG.debug("receiver ID = {}.m = {}; m = {}, sender = {}".format(self.ID, self.m, m, sender[-1]))
        #LOG.debug("SENDER = {}, TARGET = {}, order = {}".format(sender, self.ID, order))
        if self.m > 0 and m > 0:
            #print self.m
            #LOG.debug("SENDER = {}, TARGET = {}, order = {}".format(sender, self.ID, order))
            #print sender
            new_sender = [x for x in sender]
            new_sender.append(self.ID) #so you can send it out again from yourself
            #print new_sender
            self.orders.append((new_sender, order[0]))
            #LOG.debug("SENDER = {}, ID = {}, m = {}".format(sender, self.ID, self.m))
            self.m = self.m - 1 #for new iteration
            
            new_ls = [l for l in ls if ((l.ID != sender[-1]) and (l.ID != self.ID))] #n-2
            #fun OM(m-1) send value received to n-2 others
            run(self.m, new_ls, order, new_sender)
        else:
            #if Im not the one who should be sent to?
            #if sender[-1] != self.ID:
            self.orders.append((sender, order[0]))
        #print self.orders
        return

    def relay(self, ls, order, sender, m):
        for i in xrange(len(ls)):
            if ls[i] != self:
                if (self.loyalty == 'L'):
                    ls[i].receive(sender, order, ls, m)
                elif (i%2):
                    ls[i].receive(sender, order, ls, m)
                else:
                    ls[i].receive(sender, switch(order), ls, m)
        return

def run(m, new_ls, order, sender):
    #for _ in xrange(m, -1, -1):
    if m >= 0:
        for l in new_ls:
            temp = [x for x in sender]
            l.relay(new_ls, order, temp, m)
    return new_ls

def outer_run(m, ls):
    #for _ in xrange(m, -1, -1):
    for l in ls:
        print "outer run l.ID %d" % l.ID 
        l.receive([0], l.order, ls, m)
    return ls

def complete(m, ls):
    for i in xrange(len(ls)):
        condensed = condense(ls[i].orders, m)
        print condensed
        orders = sorted(condensed, key=lambda x: x[0][1])
        decisions = [order[1] for order in orders]
        print decisions[i] + ' ' + ''.join(decisions[:i]) + ' ' + ''.join(decisions[i+1:]) + ' ' + majority(decisions)
    print
    return

def spawn(L_loyalties, loyalty, m, order):
    ret = []
    for i in xrange(len(L_loyalties)):
        if loyalty == 'L':
            ret.append(General(m, L_loyalties[i], order, i+1))
        elif ((i % 2) == 0):
            ret.append(General(m, L_loyalties[i], 'A', i+1))
        else:
            ret.append(General(m, L_loyalties[i], 'R', i+1))
    return ret

def majority_t(torders):
    '''Used for Tuples'''
    dic = {'A': 0, 'R': 0, ' ': 0, 'T': 0, '-': 0}

    for order in torders:
        dic[order[1]] = dic[order[1]] + 1
    if dic['A'] == dic['R']:
        return '-'
    else:
        if dic['A'] > dic['R']:
            return 'A'
        else:
            return 'R'
def majority(orders):
    dic = {'A': 0, 'R': 0, ' ': 0, 'T': 0, '-': 0}

    for order in orders:
        dic[order[0]] = dic[order[0]] + 1
    if dic['A'] == dic['R']:
        return 'TIE'
    else:
        if dic['A'] > dic['R']:
            return 'ATTACK'
        else:
            return 'RETREAT'

def condense(orders, m):
    if m == 1:
        return orders

    longest = [order for order in orders if len(order[0]) == m + 1]
    new_orders = [order for order in orders if len(order[0]) != m + 1]

    while longest:
        to_match = longest[0][0][:-1]

        matches = [order for order in longest if order[0][:-1] == to_match]
        longest = [order for order in longest if order[0][:-1] != to_match]
        
        maj = majority_t(matches)
        
        new_orders.append((to_match, maj))

    return condense(new_orders, m - 1) 

def main(m, loyalties, order):
    ls = spawn(loyalties[1:], loyalties[0], m, order)
    
    outer_run(m, ls)
    
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
