from sys import argv
import logging

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger(__name__)

class L(object):
    """A Lieutentant in the algorithm"""
    def __init__(self, m, loyalty, order, ID, singularity=False):
        self.loyalty = loyalty
        self.m = m
        # (the first order comes when its initialized), but we add to this list without recreating
        # self.orders = {(0,ID):order[0]}
        self.orders = [order[0]]
        self.ID = ID
        self.singularity = singularity
        self.sender = (0, ID)

    def receive (self, sender, order, ls):
        self.orders.append(order[0] if self != sender else " ")
        new_ls = [l for l in ls if l != sender]
        self.relay(new_ls)
            

        # self.sender = self.sender + (sender,)
        # self.orders[self.sender] = order
        # for l in ls:
        #     if l.ID == sender:
        #         del l
        # self.relay (ls)

    # def change_m (self, new_m):
    #     self.m = new_m

    def _relay_unloyal(self, ls):
        orders = ['A' if (i%2) else 'R' for i in range(ls)]
        for l, order in zip(ls, orders):
            l.receive(self, order, ls)
            l.m -= 1

    def _relay_loyal(self, ls):
        for l in ls:
            l.receive(self, self.orders[0], ls)
            l.m -= 1

    def relay (self, ls):
        
        LOG.debug("Lieutenant ID = {}, m = {}".format(self.ID, self.m))

        if self.m >= 0:
            if self.loyalty:
                self._relay_loyal(ls)
            else:
                self._relay_unloyal(ls)

        # for i, l in enumerate(ls):
        #     if (self.ID != i):
        #         elif ((i%2) != 0):
        #             l.receive(self.ID, 'A', ls)
        #         else:
        #             l.receive(self.ID, 'R', ls)
        #     else:
        #         l.receive(self.ID, ' ', ls)
        #     l.m -= 1

        return ls #is this allowed???? I feel like its not


class C(object):
    """The Commander in the algorithm; note generals will take on this position every recurrsion"""
    def __init__(self, L_loyalties, m, loyalty, order, singularity=False):
        #singularity is purely for my own interest, can be used to see if the 
        #traitor general's orders matter
        self.loyalty = loyalty
        self.m = m
        self.order = order
        self.singularity = singularity
        self.ls = self.spawn(L_loyalties)


    def spawn (self, L_loyalties):
        ret = []
        for i in xrange(len(L_loyalties)):
            if ((self.loyalty == 'L') or (self.singularity)):
                ret.append(L(self.m - 1, L_loyalties[i], self.order, i, self.singularity))
            elif ((i % 2) == 0):
                ret.append(L(self.m - 1, L_loyalties[i], "ATTACK", i, self.singularity))
            else:
                ret.append(L(self.m - 1, L_loyalties[i], "RETREAT", i, self.singularity))
        return ret

    def run (self):
        for i in xrange (len(self.ls)):
            self.ls = self.ls[i].relay(self.ls)

    def majority (self, orders):
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

    def execute(self):
        for _ in xrange(self.m, -1, -1):
            self.run()
            for i in xrange (len(self.ls)):
                orders = self.ls[i].orders
                decision_order = self.majority(orders)
                print orders[0] + ' ' + ''.join(orders[1:]) + ' ' + decision_order


def main(m, loyalties, order):

    L_loyalties = loyalties[1:]
    commander = C(L_loyalties, m, loyalties[0], order)


    commander.execute()
            


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
