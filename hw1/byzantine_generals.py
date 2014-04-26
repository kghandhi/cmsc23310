from sys import argv



class L(object):
    """A Lieutentant in the algorithm"""
    def __init__(self, m, loyalty, order, ID, singularity = 0):
        self.loyalty = loyalty
        self.m = m
        # (the first order comes when its initialized), but we add to this list without recreating
        self.orders = {(0,ID):order[0]}
        self.ID = ID
        self.singularity = singularity
        self.sender = (0, ID)
        
    def receive (self, sender, order, ls):
        self.sender = self.sender + (sender,)
        self.orders[self.sender] = order
        self.relay (ls)

    def change_m (self, new_m):
        self.m = new_m

    def relay (self, ls):
        for i in xrange (len(ls)):
            if (self.ID != i):
                if ((self.loyalty == 'L') or (self.singularity)):
                    ls[i].receive(self.ID,self.orders[0], ls)
                    ls[i].change_m(self.m - 1)
                elif ((i%2) != 0):
                    ls[i].receive(self.ID, 'A', ls)
                    ls[i].change_m(self.m - 1)
                else:
                    ls[i].receive(self.ID, 'R', ls)
                    ls[i].change_m(self.m - 1)
            else:
                ls[i].receive(self.ID, ' ', ls)
                ls[i].change_m(self.m - 1)

        return ls #is this allowed???? I feel like its not
    

class C(object):
    """The Commander in the algorithm; note generals will take on this position every recurrsion"""
    def __init__(self, L_loyalties, m, loyalty, order, singularity = False): 
        #singularity is purely for my own interest, can be used to see if the traitor general's orders matter 
        self.loyalty = loyalty
        self.m = m
        self.order = order
        self.singularity = singularity
        self.ls = self.spawn(L_loyalties)
        

    def spawn (self, L_loyalties):
        ret = []
        for i in xrange (len(L_loyalties)):
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

    def execute (self):
        self.run()
        for i in xrange (len(self.ls)):
            orders = self.ls[i].orders
            decision_order = self.majority(orders)
            print orders[0] + ' ' + ''.join(orders[1:]) + ' ' + decision_order
            #self.ls[i].clear(decision_order)


def main(m, loyalties, order):
  
   L_loyalties = loyalties[1:]
   commander = C(L_loyalties, m, loyalties[0], order)
   
  
   for it in xrange(m):
       commander.execute()
       print


if __name__ == '__main__':
    main(int(argv[1]), list(argv[2]), argv[3])
