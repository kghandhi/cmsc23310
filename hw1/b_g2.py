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
        self.m = m-1
        self.orders = {[0]: [(0,order[0])]}
        self.ID = ID

    def receive (self, sender, order, ls):
        if sender in self.orders:
            self.orders[sender].append(order[0] if self != sender else ' ')
           
        else:
            self.orders[sender] = [(sender.ID, (order[0] if self != sender else ' '))]
            
        new_ls = [l for l in ls if (l != sender) and (l != self)]
       
        if self.m > 0:
            self.m -= 1
            run(self.m, new_ls, order, sender.append(self))
        

    def _relay_unloyal(self, ls, order):
        orders = [switch(order) if (i%2) else order for i in xrange(len(ls))]
        for l, order1 in zip(ls, orders):
            l.receive(self, order1, ls)
           
    def _relay_loyal(self, ls, order):
        for l in ls:
            l.receive(self, order, ls)
           
    def relay(self, ls, order):
        LOG.debug("Lieutenant ID = {}, m = {}".format(self.ID, self.m))

        if (self.loyalty == 'L'):
            self._relay_loyal(ls, order)
        else:
            self._relay_unloyal(ls, order)
        
        return ls

def run (m, ls, order, sender):
    for _ in xrange(m, -1, -1):
        for i in xrange (len(ls)):
            ls = ls[i].relay(ls, order)
        
    # for i in xrange(len(ls)):
    #     decision = majority(ls[i].orders)[0]
    #     ls[i].orders = ['R' if decision == 'T' else decision]
                            
    return ls

def majority_t (orders):
    dic = {'A': 0, 'R': 0, ' ': 0}
    
    for order in orders:
        dic[order[1]] = dic[order[1]] + 1
    if dic['A'] == dic['R']:
        return "TIE"
    else:
        if dic['A'] > dic['R']:
            return "ATTACK"
        else:
            return "RETREAT"
def majority(orders):
    dic = {'A': 0, 'R': 0, ' ': 0, 'T': 0}
    
    for order in orders:
        dic[order] = dic[order] + 1
    if dic['A'] == dic['R']:
        return "TIE"
    else:
        if dic['A'] > dic['R']:
            return "ATTACK"
        else:
            return "RETREAT"

def execute(m, ls, order):
    run(m, ls, order, ls[0])

    for i in xrange(1,len(ls)):
        orders = ls[i].orders
        print orders
    #     decisions = []
    #     decisions = orders[1][0][1]
    #     for j in xrange(len(ls)):
            
            
            
    #         curr = majority_t(orders[0])[0]
    #         decisions.append(curr if (curr != 'T') else 'R')
      
    #     print orders[m][0][-1] + ' ' + ''.join(decisions) + ' ' + majority(decisions)

def spawn (L_loyalties, loyalty, m, order):
    ret = [General(m, loyalty, order, 0)]
    for i in xrange(len(L_loyalties)):
        if loyalty == 'L':
            new = General(m, L_loyalties[i], order, i+1)
            ret.append(new)
        elif ((i % 2) == 0):
            ret.append(General(m, L_loyalties[i], "ATTACK", i+1))
        else:
            ret.append(General(m, L_loyalties[i], "RETREAT", i+1))
    return ret

def main(m, loyalties, order):
    #list of n-1 general lietenants, init by commander
    ls = spawn(loyalties[1:], loyalties[0], m, order)
    
    execute(m, ls, order)
    
    
if __name__ == '__main__':
    for line in open(argv[1]):
        str_m, str_loyalties, _order = line.strip('\n').split(" ")
        if((str_loyalties == _order) and _order == "END"):
            pass
        else:
            _m = int(str_m)
            _loyalties = list(str_loyalties)
            main(_m, _loyalties, _order[0])
