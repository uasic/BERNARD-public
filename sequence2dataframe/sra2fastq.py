import os

sras_directory = 'PRJNA782533_sra\\'
output = 'PRJNA782533_sra\\'
arguments = f'-O {output} --split-3  -p -v -L 6'
exe = f'F:\\sratoolkit.3.1.0-win64\\bin\\fasterq-dump.exe'
converted_sras_list = []

for sra in os.listdir(sras_directory):

    current_sra = sra
    print("SRA files: " + current_sra)
    
for sra in os.listdir(sras_directory):

    sra_directory_path = sras_directory + sra
    #print(sra_directory_path)
    current_command = f'{exe} {arguments} {sra_directory_path}'
    #print("fastq še ne obstaja")
    print("Command: " + current_command)
    os.system(current_command)
                
print(converted_sras_list)
