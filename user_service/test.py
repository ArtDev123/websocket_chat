x = [lambda: i for i in range(3)]

for i in x:
    print(i())
# print(x)

# Захватываем текущее значение i в локальную переменную arg
x = [lambda arg=i: arg for i in range(3)] 

for i in x: 
    print(i())