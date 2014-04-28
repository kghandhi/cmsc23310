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
    """A Lieutentant in the algorithm"""
    def __init__(self, m, loyalty, order, ID):
        self.loyalty = loyalty
        self.m = m - 1
        self.orders = []
        self.ID = ID
        self.order = order

    def receive(self, sender, order, ls):
        if self.m > 0:      
            self.orders.append((sender.apend(self.ID),order[0]))
            self.m -= 1
            new_ls = [l for l in ls if (l != sender) and (l != self)]
            run(self.m, new_ls, order, sender.append(self.ID))
        else:
            self.orders.append((sender, order[0]))
        

    def _relay_unloyal(self, ls):
        orders = [switch(self.orders[0]) if (i%2) else self.orders[0] for i in xrange(len(ls))]
        for l, order in zip(ls, orders):
            l.receive(self, order, ls)
           
    def _relay_loyal(self, ls):
        for l in ls:
            l.receive(self, self.orders[0], ls)
           
    def relay(self, ls):
        LOG.debug("Lieutenant ID = {}, m = {}".format(self.ID, self.m))

        if (self.loyalty == 'L'):
            self._relay_loyal(ls)
        else:
            self._relay_unloyal(ls)
        return ls

def run (m, ls):
    for _ in xrange(m-1, -1, -1):
        for i in xrange (len(ls)):
            ls = ls[i].relay(ls)
        
        # for i in xrange(len(ls)):
        #     decision = majority(ls[i].orders)[0]
        #     ls[i].orders = ['R' if decision == 'T' else decision
                            
    
    return ls

def majority (orders):
        #give it an unsorted orders list
    dic = {'A': 0, 'R': 0, ' ': 0}
    for order in orders:
        dic[order] = dic[order] + 1
    if dic['A'] == dic['R']:
        return "TIE"
    else:
        if dic['A'] > dic['R']:
            return "ATTACK"
        else:
            return "RETREAT"

def execute(m, ls):
    run(m, ls)
    for i in xrange(len(ls)):
        orders = ls[i].orders
        decision_order = majority(orders)
        print orders[0] + ' ' + ''.join(orders[1:]) + ' ' + decision_order



def spawn (L_loyalties, loyalty, m, order):
    ret = []
    for i in xrange(len(L_loyalties)):
        if loyalty == 'L':
            ret.append(General(m, L_loyalties[i], order, i))
        elif ((i % 2) == 0):
            ret.append(General(m, L_loyalties[i], "ATTACK", i))
        else:
            ret.append(General(m, L_loyalties[i], "RETREAT", i))
    return ret

def main(m, loyalties, order):
    #list of n-1 general lietenants, init by commander
    ls = spawn(loyalties[1:], loyalties[0], m, order)
    
    execute(m, ls)
    
    
if __name__ == '__main__':
    # main(int(argv[1]), list(argv[2]), argv[3])
    # argv[1] has our file..
    for line in open(argv[1]):
        str_m, str_loyalties, _order = line.strip('\n').split(" ")
        if((str_loyalties == _order) and _order == "END"):
            pass
        else:
            _m = int(str_m)
            _loyalties = list(str_loyalties)
            main(_m, _loyalties, _order[0])