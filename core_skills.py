import random
rand_list = random.sample(range(1,20),10)

list_comprehension_below_10 = [x for x in rand_list if x < 10]

list_comprehension_below_10 = list.filter(lambda x: x < 10,rand_list)