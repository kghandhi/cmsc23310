from sys import argv
import logging

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger(__name__)

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

print condense([([0,1,2],'A'), ([0,1,2], 'R')], 2)
he = []  
def relay(m,ls):
    if m > 0:
        m -= 1
        he.append(m)
        run(m,ls)
    else:
        he.append(-1)
    
def receive(m,ls):
    relay(m,ls)
  
def run(m, ls):
  for ms in xrange(m, -1 , -1):  
      for i in xrange(len(ls)):
          receive(m,ls)

run(1, ['a','b','c'])
print he
