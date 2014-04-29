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
        self.m = m-1
        self.loyalty = loyalty
        self.orders = [([0, ID], order[0])]
        self.ID = ID
        self.order = order

    def receive(self, sender, order, ls):
        if self.m > 0:
            new_sender = [x for x in sender]
            new_sender.append(self.ID)
            self.orders.append((new_sender, order[0]))
            self.m -= 1
            new_ls = [l for l in ls if (l.ID != sender[-1]) and (l.ID != self.ID)]         
            run(self.m, new_ls, order, new_sender)
        else:
            if sender[-1] != self.ID:
                self.orders.append((sender, order[0]))

    def _relay_unloyal(self, ls, order, sender):
        orders = [switch(order) if (i%2) else order for i in xrange(len(ls))]
        
        for l, order1 in zip(ls, orders):
            if l != self:
                LOG.debug("SENDER = {}, TARGET = {}, order = {}".format(sender, l.ID, order))
                temp = [x for x in sender]
                #temp.append(self.ID)
                l.receive(temp, order1, ls)

    def _relay_loyal(self, ls, order, sender):
        for l in ls:
            
            if l != self:
                
                LOG.debug("SENDER = {}, TARGET = {}, order = {}".format(sender, l.ID,order))
                temp = [x for x in sender]
                #temp.append(self.ID)
                l.receive(temp, order, ls)

    def relay(self, ls, order, sender):
        
        #LOG.debug("Lieutenant ID = {}, m = {}".format(self.ID, self.m))
        #print sender
        if (self.loyalty == 'L'):
            self._relay_loyal(ls, order, sender)
        else:
            self._relay_unloyal(ls, order, sender)

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

def run (m, ls, order, sender):
    for _ in xrange(m, -1, -1):
        for l in ls:
            
            temp = [x for x in sender]
            temp.append(l.ID)
            #print temp
            l.relay(ls, order, temp)
            #l.receive([0],order,ls)
    return
 
def majority_t(torders):
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
    dic = {'A': 0, 'R': 0, ' ': 0, '-': 0}
    
    for order in orders:
        dic[order[0]] = dic[order[0]] + 1
    if dic['A'] == dic['R']:
        return "TIE"
    else:
        if dic['A'] > dic['R']:
            return "ATTACK"
        else:
            return "RETREAT"

def condense(orders, m):
    if m == 1:
        return orders
    
    ms = [order for order in orders if len(order[0]) == m + 1]
    new_orders = [order for order in orders if len(order[0]) != m + 1]
    
    while ms:
        to_match = ms[0][0][:-1]
        matches = [order for order in ms if order[0][:-1] == to_match]
        ms = [order for order in ms if order[0][:-1] != to_match]  

        maj = majority_t(matches)
        
        new_orders.append((to_match, maj))

    return condense(new_orders, m - 1)

def execute(m, ls, order):
    run(m-1, ls, order, [0])
    
    for i in xrange(len(ls)):
        condensed = condense(ls[i].orders, m)
        orders = sorted(condensed, key=lambda x: x[0][1])
        print orders
        decisions = [order[1] for order in orders]
        print decisions[i] + ' ' + ''.join(decisions[:i]) + ' ' + ''.join(decisions[i+1:]) + ' ' + majority(decisions)
    print
    return

def main(m, loyalties, order):
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
