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
        self.m = m - 1 
        self.loyalty = loyalty
        self.orders = {}
        self.ID = ID
        self.order = (0,order)

    def receive(self, sender, order, ls):
        if sender in self.orders:
            self.orders[sender].append(order[0])
        else:
            self.orders[sender] = [order[0]]
            
        new_ls = [l for l in ls if (l != sender) and (l != self)]
       
        if self.m > 0:
            self.m -= 1
            self.order = (sender, order)
            run(self.m, new_ls, order, self)

    def _relay_unloyal(self, ls, order, sender):
        orders = [switch(order) if (i%2) else order for i in xrange(len(ls))]
        for l, order1 in zip(ls, orders):
            if l != self:
                l.receive(self, order1, ls)
           
    def _relay_loyal(self, ls, order, sender):
        for l in ls:
            if l != self:
                l.receive(sender.append(self), order, ls)
           
    def relay(self, ls, order, sender):
        LOG.debug("Lieutenant ID = {}, m = {}".format(self.ID, self.m))

        if (self.loyalty == 'L'):
            self._relay_loyal(ls, order, sender)
        else:
            self._relay_unloyal(ls, order, sender)
        
        return ls

def spawn (L_loyalties, loyalty, m, order):
    ret = [General(m, loyalty, order, 0)] #create commander
    for i in xrange(len(L_loyalties)):
        if loyalty == 'L':
            new = General(m, L_loyalties[i], order, i+1)
            ret.append(new)
        elif ((i % 2) == 0):
            ret.append(General(m, L_loyalties[i], "ATTACK", i+1))
        else:
            ret.append(General(m, L_loyalties[i], "RETREAT", i+1))
    return ret

def run (m, ls, order, sender):
    for _ in xrange(m, -1, -1):
        for i in xrange(1, len(ls)):
            ls = ls[i].relay(ls, order, sender)
    return ls

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
    for i in xrange(1, len(ls)):
        print ls[i].orders
        #for j in xrange(len(ls)):
           
            
def main(m, loyalties, order):
    ls = spawn(loyalties[1:], loyalties[0], m, order)
    for i in xrange(1, len(ls)):
        ls[i].receive([ls[0]], ls[i].order, ls)

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
