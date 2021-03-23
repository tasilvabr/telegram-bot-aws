import json
import os
import logging
import boto3
from datetime import datetime,timedelta, date
from botocore.vendored import requests

#Environment Variables
TOKEN = os.environ['TOKEN']
URL = "https://api.telegram.org/bot{}/".format(TOKEN)
INFRA_GROUP = str(os.environ['INFRA_GROUP_ID'])
SESSION_TIMEOUT = os.environ['SESSION_TIMEOUT_MINUTES']
USER_TABLE = os.environ['USER_TABLE']
SESSION_TABLE = os.environ['SESSION_TABLE']
REGION_DB = os.environ['REGION_DB']
SERVICES = ['EC2','Snapshot']

date_hour = datetime.now()
hour = (int(date_hour.strftime('%H'))-3)
salutation = ""
exit = ""

def lambda_handler(event, context):
    global salutation
    
    if (hour>=0 and hour<6):
        salutation="Boa madrugada,"
        exit="tenha uma boa madrugada!"
    elif (hour>=6 and hour<12):
        salutation="Bom dia,"
        exit="tenha um bom dia!"
    elif (hour>=12 and hour<18):
        salutation="Boa tarde,"
        exit="tenha uma boa tarde!"
    else:
        salutation="Boa noite,"
        exit="tenha uma boa noite!"
        
    message=json.loads(event['body'])
    #message=event
    from_user=dict(message['message']['from'])
    from_user_id=str(from_user['id'])
    try:
        from_user_name=str(str(from_user['first_name']) + ' ' + str(from_user['last_name']))
    except:
        from_user_name=str(str(from_user['first_name']))

    chat_id=message['message']['chat']['id']
    reply=message['message']['text']
    
    permitted=0
    
    response = user_exists(from_user_id)
    keys = list([key for key in response.keys()])
    if 'Item' not in keys:
        try:
            response = user_put(from_user_id, from_user_name, "Guest", "denied")
            
            salutation_denied(reply,from_user_id,from_user_name)
            
            
            return {
                   'statusCode': 200
            }
        except:
            pass

    else:
        job = response["Item"]["job"]["S"]
        status = response["Item"]["status_user"]["S"]
        
        if (status=="allowed"):
            permitted=1
    
    if (permitted==1):
        date_hour = datetime.now()
        date_time = datetime.today() - timedelta(minutes=int(SESSION_TIMEOUT))
        response = session_exists(from_user_id, date_time)
        new_session = False
        if len(response['Item'])==0:
            try:
                if (reply.strip()!="/start"):
                    final_text='Sessão Expirada!\n\n'
                    url = URL + "sendMessage?text={}&chat_id={}".format(final_text,from_user_id)
                    requests.get(url)
                commands="/start"
                session_id = from_user_id + date_hour.strftime('%y%m%d%H%M%S%f')
                response = session_create(from_user_id, session_id, date_hour, commands)
                new_session = True
            except:
                pass
        
        else:
            try:
                session_id = response['Item']['session_id']
                commands = response['Item']['commands']
                all_commands = commands.split(',')
                previous_command = all_commands[-1]

            except:
                return {
                    "statusCode": 200
                }

        if (new_session):
            salutation_allowed(from_user_id,from_user_name)
            menu_principal(chat_id,job)
        
        else:
            if (reply.strip().lower() == 'voltar'):
                all_commands.pop()
                reply=all_commands.pop()
                if (len(all_commands)==0):
                    previous_command = reply
                else:
                    previous_command = all_commands[-1]
                
                commands=''
                if (len(all_commands)==0):
                    commands=reply
                else:
                    for com in all_commands:
                        if commands=='':
                            commands = com
                        else:
                            commands += ',' + com
                
                date_hour = datetime.now()
                response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
            
            if (reply.strip().lower() == 'sair' and not new_session):
                commands += ','+reply.strip()
                date_hour = datetime.now()
                response = session_update(chat_id, session_id, date_hour, commands, 'encerrada')
                buttons={}
                buttons['remove_keyboard']=True
                buttons['selective']=False
        
                reply_kb_markup = json.dumps(buttons, indent = 4)
                    
                final_text=from_user_name + ", sessão do bot finalizada" 
                url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,from_user_id,reply_kb_markup)
                requests.get(url)
                final_text="Para iniciar nova sessão digite '/start', obrigado!"
                url = URL + "sendMessage?text={}&chat_id={}".format(final_text,from_user_id)
                requests.get(url)
                final_text = exit
                url = URL + "sendMessage?text={}&chat_id={}".format(final_text,from_user_id)
                requests.get(url)
            
            elif ((reply.strip().lower() == 'usuários' or previous_command.strip().lower()[:8] == 'usuários') and job=='Adm'):
                reply = reply.split('|')[-1]
                users(reply.strip(), previous_command.strip(), chat_id, job, commands, session_id)
            
            else:
                if (reply.strip().upper() in SERVICES or reply.strip() in SERVICES):
                    commands += ','+reply.strip()
                    date_hour = datetime.now()
                    response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
                    send_message(reply, chat_id, previous_command)
                
                else:
                    if (previous_command.upper() in SERVICES):
                        reply = reply.split('|')[-1]
                        action=str(previous_command + '|' + reply.strip()).split('|')
                        send_message_action(reply.strip(), chat_id, action, commands, previous_command, session_id, job)
                    else:
                        verify_service=str(previous_command).split('|')
                        if (verify_service[0] in SERVICES):
                            action=str(previous_command + '|' + reply.strip()).split('|')
                            send_message_action(reply.strip(), chat_id, action, commands, previous_command, session_id, job)
                        else:
                            menu_principal(chat_id,job)
                    
        return {
        'statusCode': 200
            
        }

    else:
        return {
               'statusCode': 200
        }
        
def send_message(text, chat_id, previous):
    
    if (text.lower() == 'ec2'):
        buttons={}
        buttons['keyboard']=[[]]
        ec2 = boto3.resource('ec2')
        cont = 1
        array = 0
        for instance in ec2.instances.all():
            state=instance.state['Code']
            if (state!=32 and state!=48):
                if (state == 16 or state == 0):
                    condition="on"
                elif (state == 80 or state == 64):
                    condition="off"
                    
                if cont<=2:
                    
                    buttons['keyboard'][array].append({'text':'{} - {}'.format(instance.tags[0]['Value'],condition)})
                    cont+=1
                    
                else:
                    buttons['keyboard'].append([])
                    cont=1
                    array+=1
                    buttons['keyboard'][array].append({'text':'{} - {}'.format(instance.tags[0]['Value'],condition)})
                    cont+=1
        
        buttons['keyboard'].append([])   
        array+=1
        buttons['keyboard'][array].append({'text':'Voltar'})
        
        buttons['keyboard'].append([])
        array+=1
        buttons['keyboard'][array].append({'text':'Sair'})
                
        buttons['resize_keyboard']=True
        buttons['one_time_keyboard']=True
        buttons['selective']=True
        
        reply_kb_markup = json.dumps(buttons, indent = 4)
                
        final_text="Escolha a EC2"
        url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
        requests.get(url)
    
    if (text.lower() == 'snapshot'):
        buttons={}
        buttons['keyboard']=[[]]
        ec2 = boto3.client('ec2', region_name='us-east-1')
        cont = 1
        array = 0
        snapshots = ec2.describe_snapshots(OwnerIds=['self']) 
        for snapshot in snapshots['Snapshots']:
            if cont<=1:
                buttons['keyboard'][array].append({'text':'{}'.format(snapshot['Description'])})
                cont+=1
                
            else:
                buttons['keyboard'].append([])
                cont=1
                array+=1
                buttons['keyboard'][array].append({'text':'{}'.format(snapshot['Description'])})
                cont+=1
        
        buttons['keyboard'].append([])   
        array+=1
        buttons['keyboard'][array].append({'text':'Voltar'})
        
        buttons['keyboard'].append([])
        array+=1
        buttons['keyboard'][array].append({'text':'Sair'})
                
        buttons['resize_keyboard']=True
        buttons['one_time_keyboard']=True
        buttons['selective']=True
        
        reply_kb_markup = json.dumps(buttons, indent = 4)
                
        final_text="Escolha o Snapshot"
        url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
        requests.get(url)

def send_message_action(text, chat_id, action, commands, previous, session_id, job):
    tam=len(action)
    if (tam==2 and action[0].lower()=='ec2'):
        action[1]=action[1].split()[0]
        buttons={}
        buttons['keyboard']=[[]]
        ec2 = boto3.resource('ec2')
        array = 0
        anyEC2=False
        for instance in ec2.instances.all():
            if instance.tags[0]['Value']==action[1]:
                command = previous + '|' + text
                commands += ','+command
                date_hour = datetime.now()
                response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
                state=int(instance.state['Code'])
                if state==0:
                    status="pendente"
                elif state==16:
                    status="ligada"
                elif state==32:
                    status="desligando"
                elif state==48:
                    status="encerrada"
                elif state==64:
                    status="parando"
                elif state==80:
                    status="desligada"

                if state==80 or state==64:
                    buttons['keyboard'][array].append({'text':'{}'.format('Ligar')})
                    anyEC2=True
                    
                elif state==16 or state==0:
                    buttons['keyboard'][array].append({'text':'{}'.format('Desligar')})
                    buttons['keyboard'].append([])   
                    array+=1
                    buttons['keyboard'][array].append({'text':'Reiniciar'})
                    anyEC2=True
        
        buttons['keyboard'].append([])   
        array+=1
        buttons['keyboard'][array].append({'text':'Descrição'})     
        
        buttons['keyboard'].append([])   
        array+=1
        buttons['keyboard'][array].append({'text':'Criar Snapshot'})     
        
        buttons['keyboard'].append([])   
        array+=1
        buttons['keyboard'][array].append({'text':'Voltar'})     
        
        buttons['keyboard'].append([])
        array+=1
        buttons['keyboard'][array].append({'text':'Sair'})

        buttons['resize_keyboard']=True
        buttons['one_time_keyboard']=True
        buttons['selective']=True
        
        reply_kb_markup = json.dumps(buttons, indent = 4)
        
        final_text="Sua instância {} está {}".format(str(action[1]),status)
        
        if (anyEC2 == True):
            url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
            requests.get(url)
            
        else:
            final_text = final_text + " - Opção indisponível!"
            url = URL + "sendMessage?text={}&chat_id={}".format(final_text,chat_id)
            requests.get(url)
            
    elif (tam==3 and action[0].lower()=='ec2'):
        action[1]=action[1].split()[0]
        ec2 = boto3.resource('ec2')
        for instance in ec2.instances.all():
            if instance.tags[0]['Value']==action[1]:
                az=instance.placement['AvailabilityZone']
                region_es2=az[:-1]
                if action[2]=='Ligar':
                    command = previous + '|' + text
                    commands  += ','+command
                    date_hour = datetime.now()
                    response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
                    
                    ec2 = boto3.client('ec2', region_name=region_es2)
                    instancias=[]
                    instancias.append(instance.id)
                    ec2.start_instances(InstanceIds=instancias)

                    buttons={}
                    buttons['keyboard']=[[]]
                    array = 0
                    buttons['keyboard'][array].append({'text':'Voltar'})     
                    
                    buttons['keyboard'].append([])
                    array+=1
                    buttons['keyboard'][array].append({'text':'Sair'})
            
                    buttons['resize_keyboard']=True
                    buttons['one_time_keyboard']=True
                    buttons['selective']=True
        
                    reply_kb_markup = json.dumps(buttons, indent = 4)
                    
                    final_text="Sua instância foi ligada com sucesso!"
                    url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
                    requests.get(url) 

                if action[2]=='Desligar':
                    command = previous + '|' + text
                    commands  += ','+command
                    date_hour = datetime.now()
                    response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
                    
                    ec2 = boto3.client('ec2', region_name=region_es2)
                    instancias=[]
                    instancias.append(instance.id)
                    ec2.stop_instances(InstanceIds=instancias)
                     
                    buttons={}
                    buttons['keyboard']=[[]]
                    array = 0
                    buttons['keyboard'][array].append({'text':'Voltar'})     
                    
                    buttons['keyboard'].append([])
                    array+=1
                    buttons['keyboard'][array].append({'text':'Sair'})
            
                    buttons['resize_keyboard']=True
                    buttons['one_time_keyboard']=True
                    buttons['selective']=True
        
                    reply_kb_markup = json.dumps(buttons, indent = 4)
                    
                    final_text="Sua instância foi desligada com sucesso!"
                    url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
                    requests.get(url) 
                
                if action[2]=='Reiniciar':
                    command = previous + '|' + text
                    commands  += ','+command
                    date_hour = datetime.now()
                    response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
                    
                    ec2 = boto3.client('ec2', region_name=region_es2)
                    instancias=[]
                    instancias.append(instance.id)
                    ec2.reboot_instances(InstanceIds=instancias)
                     
                    buttons={}
                    buttons['keyboard']=[[]]
                    array = 0
                    buttons['keyboard'][array].append({'text':'Voltar'})     
                    
                    buttons['keyboard'].append([])
                    array+=1
                    buttons['keyboard'][array].append({'text':'Sair'})
            
                    buttons['resize_keyboard']=True
                    buttons['one_time_keyboard']=True
                    buttons['selective']=True
        
                    reply_kb_markup = json.dumps(buttons, indent = 4)
                    
                    final_text="Sua instância foi reiniciada com sucesso!"
                    url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
                    requests.get(url)
                
                if action[2]=='Descrição':
                    command = previous + '|' + text
                    commands  += ','+command
                    date_hour = datetime.now()
                    response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
                    
                    ec2 = boto3.client('ec2', region_name=region_es2)
                    instancias=[]
                    instancias.append(instance.id)
                    description_instance = ec2.describe_instances(InstanceIds=instancias)['Reservations'][0]['Instances']
                    response=""
                    stateCode = description_instance[0]['State']['Code']
                    if stateCode==0:
                        state="pendente"
                    elif stateCode==16:
                        state="ligada"
                    elif stateCode==32:
                        state="desligando"
                    elif stateCode==48:
                        state="encerrada"
                    elif stateCode==64:
                        state="parando"
                    elif stateCode==80:
                        state="desligada"
                    for tag in description_instance[0]['Tags']:
                        if (tag['Key'] == 'Name'):
                            response = "Nome: " + tag['Value'] + "\n\n"
                            break
                    
                    for tag in description_instance[0]['Tags']:
                        if (tag['Key'] != 'Name'):
                            response += "Tag: " + tag['Key'] + ": " + tag['Value'] + "\n"
                    response += "AMI: " + description_instance[0]['ImageId'] + "\n"
                    response += "ID Instância: " + description_instance[0]['InstanceId'] + "\n"
                    response += "Tipo: " + description_instance[0]['InstanceType'] + "\n"
                    response += "Chave: " + description_instance[0]['KeyName'] + "\n"
                    response += "Estado: " + state + "\n"
                    response += "Região: " + description_instance[0]['Placement']['AvailabilityZone'][:-1] + "\n"
                    response += "AZ: " + description_instance[0]['Placement']['AvailabilityZone'] + "\n"
                    response += "IP Privado: " + description_instance[0]['PrivateIpAddress'] + "\n"
                    try:
                        response += "DNS Público: " + description_instance[0]['PublicDnsName'] + "\n"
                        response += "IP Público: " + description_instance[0]['PublicIpAddress'] + "\n"
                    except:
                        pass
                    for volume in description_instance[0]['BlockDeviceMappings']:
                        response += "Volume 1: " + volume['Ebs']['VolumeId'] + "\n"
                    
                    buttons={}
                    buttons['keyboard']=[[]]
                    array = 0
                    buttons['keyboard'][array].append({'text':'Voltar'})     
                    
                    buttons['keyboard'].append([])
                    array+=1
                    buttons['keyboard'][array].append({'text':'Sair'})
            
                    buttons['resize_keyboard']=True
                    buttons['one_time_keyboard']=True
                    buttons['selective']=True
        
                    reply_kb_markup = json.dumps(buttons, indent = 4)

                    url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(response,chat_id,reply_kb_markup)
                    requests.get(url)  

                if action[2]=='Criar Snapshot':
                    command = previous + '|' + text
                    commands  += ','+command

                    instanceSnapshot = boto3.client('ec2', region_name=region_es2)
                    
                    date_hour = datetime.now()
                    description = 'Snapshot Bot EC2 ' + action[1] + ' ' + date_hour.strftime('%y-%m-%d %H:%S')

                    response = instanceSnapshot.create_snapshots(
                        Description=description,
                        InstanceSpecification={
                            'InstanceId': str(instance.id),
                            'ExcludeBootVolume': False
                        },
                        CopyTagsFromSource='volume'
                    )
                    
                    buttons={}
                    buttons['keyboard']=[[]]
                    array = 0
                    buttons['keyboard'][array].append({'text':'Voltar'})     
                    
                    buttons['keyboard'].append([])
                    array+=1
                    buttons['keyboard'][array].append({'text':'Sair'})
            
                    buttons['resize_keyboard']=True
                    buttons['one_time_keyboard']=True
                    buttons['selective']=True
        
                    reply_kb_markup = json.dumps(buttons, indent = 4)
                    
                    date_hour = datetime.now()
                    response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
                    
                    final_text="{} criado com sucesso!".format(str(description))
                    url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
                    requests.get(url)

    elif (tam==2 and action[0].lower()=='snapshot'):
        ec2 = boto3.client('ec2', region_name='us-east-1')
        cont = 1
        array = 0
        snapshots = ec2.describe_snapshots(OwnerIds=['self']) 
        for snapshot in snapshots['Snapshots']:
            if (snapshot['Description'] == action[1]):
                snap = snapshot
                break

        final_text = "Descrição: " + snapshot['Description'] + "\n"
        final_text += "SnapshotId: " + snapshot['SnapshotId'] + "\n"
        final_text += "Data: " + str(snapshot['StartTime']) + "\n"
        final_text += "VolumeId: " + snapshot['VolumeId'] + "\n"
        final_text += "Tamanho: " + str(snapshot['VolumeSize']) + " Gb\n"
        final_text += "Tag Name: " + snapshot['Tags'][0]['Value']
        url = URL + "sendMessage?text={}&chat_id={}".format(final_text,chat_id)
        requests.get(url)
            
        buttons={}
        buttons['keyboard']=[[]]
        array = 0
        command = previous + '|' + text
        commands += ','+command
        date_hour = datetime.now()
        response = session_update(chat_id, session_id, date_hour, commands, 'aberta')

        buttons['keyboard'][array].append({'text':'Excluir'})   
        
        buttons['keyboard'].append([])
        cont=1
        array+=1
        buttons['keyboard'][array].append({'text':'Voltar'})
        
        buttons['keyboard'].append([])
        cont=1
        array+=1
        buttons['keyboard'][array].append({'text':'Sair'})

        buttons['resize_keyboard']=True
        buttons['one_time_keyboard']=True
        buttons['selective']=True
        
        reply_kb_markup = json.dumps(buttons, indent = 4)
        
        final_text="Selecione uma opção"
        url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
        requests.get(url)

    elif (tam==3 and action[0].lower()=='snapshot'):
        ec2 = boto3.client('ec2', region_name='us-east-1')
        cont = 1
        array = 0
        snapshots = ec2.describe_snapshots(OwnerIds=['self']) 
        for snapshot in snapshots['Snapshots']:
            if (snapshot['Description'] == action[1]):
                snap = snapshot
                break
        
        if (snap != None):
            buttons={}
            buttons['keyboard']=[[]]
            array = 0
            command = previous + '|' + text
            commands += ','+command
            date_hour = datetime.now()
            response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
    
            buttons['keyboard'][array].append({'text':'Sim'})   
            
            buttons['keyboard'].append([])
            cont=1
            array+=1
            buttons['keyboard'][array].append({'text':'Não'})
            
            buttons['keyboard'].append([])
            cont=1
            array+=1
            buttons['keyboard'][array].append({'text':'Voltar'})
            
            buttons['keyboard'].append([])
            cont=1
            array+=1
            buttons['keyboard'][array].append({'text':'Sair'})
    
            buttons['resize_keyboard']=True
            buttons['one_time_keyboard']=True
            buttons['selective']=True
            
            reply_kb_markup = json.dumps(buttons, indent = 4)
            
            final_text="Tem certeza que deseja excluir o snapshot {} ?".format(action[1])
            url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
            requests.get(url)
    
    elif (tam==4 and action[0].lower()=='snapshot'):
        ec2 = boto3.client('ec2', region_name='us-east-1')
        cont = 1
        array = 0
        snapshots = ec2.describe_snapshots(OwnerIds=['self']) 
        for snapshot in snapshots['Snapshots']:
            if (snapshot['Description'] == action[1]):
                snap = snapshot
                break
        
        if (snap != None):
            if (action[3]=="Sim"):
                ec2.delete_snapshot(SnapshotId=snap['SnapshotId'])
            
                buttons={}
                buttons['keyboard']=[[]]
                array = 0
                command = previous + '|' + text
                commands += ','+command
                date_hour = datetime.now()
                response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
        
                buttons['keyboard'][array].append({'text':'Voltar'})
                
                buttons['keyboard'].append([])
                cont=1
                array+=1
                buttons['keyboard'][array].append({'text':'Sair'})
        
                buttons['resize_keyboard']=True
                buttons['one_time_keyboard']=True
                buttons['selective']=True
                
                reply_kb_markup = json.dumps(buttons, indent = 4)
                
                final_text="O snapshot {} foi excluído com sucesso!".format(action[1])
                url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
                requests.get(url)
            else:
                buttons={}
                buttons['keyboard']=[[]]
                array = 0
                command = previous + '|' + text
                commands += ','+command
                date_hour = datetime.now()
                response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
        
                buttons['keyboard'][array].append({'text':'Voltar'})
                
                buttons['keyboard'].append([])
                cont=1
                array+=1
                buttons['keyboard'][array].append({'text':'Sair'})
        
                buttons['resize_keyboard']=True
                buttons['one_time_keyboard']=True
                buttons['selective']=True
                
                reply_kb_markup = json.dumps(buttons, indent = 4)
                
                final_text="O snapshot {} não foi excluído!".format(action[1])
                url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
                requests.get(url)

    else:
        menu_principal(chat_id,job)

def user_exists(user_id):
    dynamodb = boto3.client('dynamodb')
    response = dynamodb.get_item(TableName=USER_TABLE, Key={'user_id':{'S':str(user_id)}})
    return response

def user_put(user_id, name, job, status):
    dynamodb = boto3.resource('dynamodb', region_name=REGION_DB)
    table = dynamodb.Table(USER_TABLE)
    response = table.put_item(
    Item={
            "user_id": str(user_id),
            "name": str(name),
            "job": str(job),
            "status_user": status
        }
    )
    return response

def user_update(user_id, name, job, status):
    dynamodb = boto3.resource('dynamodb', region_name=REGION_DB)
    table = dynamodb.Table(USER_TABLE)
    response = table.update_item(
        Key={
            'user_id': str(user_id)
        },
        UpdateExpression="set name = :nameUp, job = :jobUp, status_user = :statusUp ",
        ExpressionAttributeValues={
            ':nameUp': str(name),
            ':jobUp': str(job),
            ':statusUp':status
            
        },
        ReturnValues="UPDATED_NEW"
        )
    
    return response

def allow_user(user):
    dynamodb = boto3.resource('dynamodb', region_name=REGION_DB)
    table = dynamodb.Table(USER_TABLE)
    response = table.update_item(
        Key={
            'user_id': str(user['user_id']['S'])
        },
        UpdateExpression="set status_user = :statusUp ",
        ExpressionAttributeValues={
            ':statusUp':'allowed'
            
        },
        ReturnValues="UPDATED_NEW"
        )

    return response

def deny_user(user):
    dynamodb = boto3.resource('dynamodb', region_name=REGION_DB)
    table = dynamodb.Table(USER_TABLE)
    response = table.update_item(
        Key={
            'user_id': str(user['user_id']['S'])
        },
        UpdateExpression="set status_user = :statusUp ",
        ExpressionAttributeValues={
            ':statusUp':'denied'
            
        },
        ReturnValues="UPDATED_NEW"
        )
    
    return response

def user_delete(user):
    dynamodb = boto3.resource('dynamodb', region_name=REGION_DB)
    table = dynamodb.Table(USER_TABLE)
    response = table.delete_item(
        Key={
            'user_id': str(user['user_id']['S'])
        }
        )

def user_denied():
    dynamodb = boto3.client('dynamodb')
    response = dynamodb.query(
        TableName=USER_TABLE,
        IndexName= "statusUser",
        KeyConditionExpression='status_user = :statusF ',
        ExpressionAttributeValues={
            ':statusF': {'S': 'denied'}
        }
    )
    return(response['Items'])
    
def user_allowed():
    dynamodb = boto3.client('dynamodb')
    response = dynamodb.query(
        TableName=USER_TABLE,
        IndexName= "statusUser",
        KeyConditionExpression='status_user = :statusF ',
        ExpressionAttributeValues={
            ':statusF': {'S': 'allowed'}
        }
    )
    return(response['Items'])

def session_exists(user_id, date_time):
    dynamodb = boto3.client('dynamodb')
    response = dynamodb.query(
        TableName=SESSION_TABLE,
        IndexName= "dateHour",
        KeyConditionExpression='user_id = :userId AND date_hour > :dateHourVerify ',
        ExpressionAttributeValues={
            ':userId': {'S': str(user_id)},
            ':dateHourVerify': {'S': str(date_time)}
        }
    )

    if len(response['Items'])>0:
        session={
            "user_id": user_id,
            "session_id":"",
            "date_hour":date_time,
            "commands":"",
            "status_session":"aberta"
        }
        for item in response['Items']:
            if (datetime.strptime(item['date_hour']['S'], '%Y-%m-%d %H:%M:%S.%f') >= date_time and datetime.strptime(item['date_hour']['S'], '%Y-%m-%d %H:%M:%S.%f') >=session['date_hour'] and item['status_session']['S'] == 'aberta'):
                session={
                    "user_id": item['user_id']['S'],
                    "session_id": item['session_id']['S'],
                    "date_hour":item['date_hour']['S'],
                    "commands":item['commands']['S'],
                    "status_session":item['status_session']['S'],
                }
        
        if session['session_id'] == '':
            return {
                "Item":{}
                
            }

        return {
            "Item":session
        }
            
    return {
        "Item":{}
    }

def session_create(user_id, session_id, date_hour, commands, status="aberta"):
    dynamodb = boto3.resource('dynamodb', region_name=REGION_DB)
    table = dynamodb.Table(SESSION_TABLE)
    response = table.put_item(
    Item={
            "user_id": str(user_id),
            "session_id": str(session_id),
            "date_hour": str(date_hour),
            "commands": str(commands),
            "status_session": str(status)
        }
    )
    return response

def session_update(user_id, session_id, date_hour, commands, status):
    dynamodb = boto3.resource('dynamodb', region_name=REGION_DB)
    table = dynamodb.Table(SESSION_TABLE)
    response = table.update_item(
        Key={
            'user_id': str(user_id),
            'session_id': str(session_id)
            
        },
        UpdateExpression="set date_hour = :dateHour, commands = :commandsUp, status_session = :statusUp ",
        ExpressionAttributeValues={
            ':dateHour': str(date_hour),
            ':commandsUp':str(commands),
            ':statusUp':str(status)
            
        },
        ReturnValues="UPDATED_NEW"
        )
    
    return response

def salutation_denied(text,from_user_id,from_user_name):
    if (str(text).lower() in  ('/start','iniciar','start','menu','oi','ola','olá','bot','aws')):
        final_text=salutation
        url = URL + "sendMessage?text={}&chat_id={}".format(final_text,from_user_id)
        requests.get(url)
                
        final_text="Seja bem vindo ao Bot, " + from_user_name
        url = URL + "sendMessage?text={}&chat_id={}".format(final_text,from_user_id)
        requests.get(url)
                
        final_text="Seu acesso não está liberado!"
        url = URL + "sendMessage?text={}&chat_id={}".format(final_text,from_user_id)
        requests.get(url)
                
        if (INFRA_GROUP != '0'):
            final_text="**Tentativa de uso não autorizado do Bot**"
            url = URL + "sendMessage?text={}&chat_id={}".format(final_text,INFRA_GROUP)
            requests.get(url)
                    
            final_text="Usuário: " + from_user_name + " (" + from_user_id + ")"
            url = URL + "sendMessage?text={}&chat_id={}".format(final_text,INFRA_GROUP)
            requests.get(url)
                    
            final_text="Acesso foi bloqueado!"
            url = URL + "sendMessage?text={}&chat_id={}".format(final_text,INFRA_GROUP)
            requests.get(url)
                
    else:
        final_text="Seu acesso não está liberado!"
        url = URL + "sendMessage?text={}&chat_id={}".format(final_text,from_user_id)
        requests.get(url)
                
        if (INFRA_GROUP != '0'):
            final_text="**Tentativa de uso não autorizado do Bot**"
            url = URL + "sendMessage?text={}&chat_id={}".format(final_text,INFRA_GROUP)
            requests.get(url)
                    
            final_text="Usuário: " + from_user_name + "(" + from_user_id + ")"
            url = URL + "sendMessage?text={}&chat_id={}".format(final_text,INFRA_GROUP)
            requests.get(url)
                    
            final_text="Acesso foi bloqueado!"
            url = URL + "sendMessage?text={}&chat_id={}".format(final_text,GRUPO_INFRA)
            requests.get(url)

def salutation_allowed(from_user_id,from_user_name):
    final_text=salutation
    url = URL + "sendMessage?text={}&chat_id={}".format(final_text,from_user_id)
    requests.get(url)
            
    final_text="Seja bem vindo ao Bot, " + from_user_name
    url = URL + "sendMessage?text={}&chat_id={}".format(final_text,from_user_id)
    requests.get(url)
            
    if (str(INFRA_GROUP) != '0'):
        final_text="*Uso autorizado do Bot*"
        url = URL + "sendMessage?text={}&chat_id={}".format(final_text,INFRA_GROUP)
        requests.get(url)
                
        final_text="Usuário: " + from_user_name
        url = URL + "sendMessage?text={}&chat_id={}".format(final_text,INFRA_GROUP)
        requests.get(url)
                
        final_text="Acesso liberado!"
        url = URL + "sendMessage?text={}&chat_id={}".format(final_text,INFRA_GROUP)
        requests.get(url)
        
def menu_principal(chat_id, job):
    buttons={}
    buttons['keyboard']=[[]]
    array = 0
    count = 1
            
    for service in SERVICES:
        if count<=2:
            buttons['keyboard'][array].append({'text':service})
            count+=1
                    
        else:
            buttons['keyboard'].append([])
            count=1
            array+=1
            buttons['keyboard'][array].append({'text':service})
            count+=1
                
    if (job == 'Adm'):
        buttons['keyboard'].append([])
        array+=1
        buttons['keyboard'][array].append({'text':'Usuários'})
        
    buttons['keyboard'].append([])
    array+=1
    buttons['keyboard'][array].append({'text':'Sair'})
                
    buttons['resize_keyboard']=True
    buttons['one_time_keyboard']=True
    buttons['selective']=True
            
    reply_kb_markup = json.dumps(buttons, indent = 4)
            
    final_text="Selecione o serviço da AWS"
    url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
    requests.get(url) 
    

def users(command, previous, chat_id, job, commands, session_id):
    if (command.lower() == 'usuários'):
        action = command
    
    elif (previous.lower()[:8] == 'usuários'):
        action = previous + '|' + command

    commands  += ','+action

    action = action.split('|')
    
    if (len(action)==1):
        buttons={}
        array=0
        buttons['keyboard']=[[]]

        buttons['keyboard'][array].append({'text':'Liberar'})
        buttons['keyboard'][array].append({'text':'Bloquear'})

        buttons['keyboard'].append([])
        array+=1
        buttons['keyboard'][array].append({'text':'Voltar'})
        
        buttons['keyboard'].append([])
        array+=1
        buttons['keyboard'][array].append({'text':'Sair'})
                    
        buttons['resize_keyboard']=True
        buttons['one_time_keyboard']=True
        buttons['selective']=True
                
        reply_kb_markup = json.dumps(buttons, indent = 4)
                
        final_text="Selecione uma opção"
        url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
        requests.get(url)
        
        date_hour = datetime.now()
        response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
    
    elif (len(action)==2) and action[0].lower() == 'usuários' and action[1].lower()=='liberar':
        denied_users = [user['name']['S']+' ('+user['user_id']['S']+')' for user in user_denied()]
        buttons={}
        buttons['keyboard']=[[]]
        array = 0
        count = 1
            
        for user in denied_users:
            if count<=2:
                buttons['keyboard'][array].append({'text':user})
                count+=1
                        
            else:
                buttons['keyboard'].append([])
                count=1
                array+=1
                buttons['keyboard'][array].append({'text':user})
                count+=1
                    
        buttons['keyboard'].append([])
        array+=1
        buttons['keyboard'][array].append({'text':'Voltar'})
        
        buttons['keyboard'].append([])
        array+=1
        buttons['keyboard'][array].append({'text':'Sair'})
                    
        buttons['resize_keyboard']=True
        buttons['one_time_keyboard']=True
        buttons['selective']=True
                
        reply_kb_markup = json.dumps(buttons, indent = 4)
                
        final_text="Selecione o usuário"
        url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
        requests.get(url)
        
        date_hour = datetime.now()
        response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
        
    elif (len(action)==3  and action[0].lower() == 'usuários' and action[1].lower()=='liberar'):
        denied_users = [user['name']['S']+' ('+user['user_id']['S']+')' for user in user_denied()]
        if (action[2] in denied_users):
            buttons={}
            array=0
            buttons['keyboard']=[[]]
            buttons['keyboard'][array].append({'text':'Liberar'})
            buttons['keyboard'][array].append({'text':'Excluir'})
            buttons['keyboard'].append([])
            array+=1
            buttons['keyboard'][array].append({'text':'Voltar'})
            buttons['keyboard'].append([])
            array+=1
            buttons['keyboard'][array].append({'text':'Sair'})
                        
            buttons['resize_keyboard']=True
            buttons['one_time_keyboard']=True
            buttons['selective']=True
                    
            reply_kb_markup = json.dumps(buttons, indent = 4)
                    
            final_text="Selecione uma opção"
            url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
            requests.get(url)
            
            date_hour = datetime.now()
            response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
        else:
            buttons={}
            buttons['keyboard']=[[]]
            array = 0
            count = 1
                
            for user in denied_users:
                if count<=2:
                    buttons['keyboard'][array].append({'text':user})
                    count+=1
                            
                else:
                    buttons['keyboard'].append([])
                    count=1
                    array+=1
                    buttons['keyboard'][array].append({'text':user})
                    count+=1
                        
            buttons['keyboard'].append([])
            array+=1
            buttons['keyboard'][array].append({'text':'Voltar'})
            
            buttons['keyboard'].append([])
            array+=1
            buttons['keyboard'][array].append({'text':'Sair'})
                        
            buttons['resize_keyboard']=True
            buttons['one_time_keyboard']=True
            buttons['selective']=True
                    
            reply_kb_markup = json.dumps(buttons, indent = 4)
                    
            final_text="Selecione o usuário"
            url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
            requests.get(url)
    
    elif (len(action)==4 and action[0].lower() == 'usuários' and action[1].lower()=='liberar'):
        denied_users = [user['name']['S']+' ('+user['user_id']['S']+')' for user in user_denied()]
        
        if (action[2] in denied_users):
            
            if (action[3].lower() in ('liberar','excluir')):
                
                if (action[3].lower() == 'liberar'):
                    userId = action[2][(action[2].index('(')+1):-1]
                    response = user_exists(userId)
                    keys = list([key for key in response.keys()])
                    if 'Item' in keys:
                        user = response['Item']
                        try:
                            allow_user(user)
                            final_text=salutation
                            url = URL + "sendMessage?text={}&chat_id={}".format(final_text,user['user_id']['S'])
                            requests.get(url)
                            final_text=user['name']['S'] + ", seu usuário foi liberado"
                            url = URL + "sendMessage?text={}&chat_id={}".format(final_text,user['user_id']['S'])
                            requests.get(url)
                            final_text="Digite '/start' para iniciar o bot"
                            url = URL + "sendMessage?text={}&chat_id={}".format(final_text,user['user_id']['S'])
                            requests.get(url)
                            date_hour = datetime.now()
                            response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
                            final_text="Usuário liberado com sucesso"
                            url = URL + "sendMessage?text={}&chat_id={}".format(final_text,chat_id)
                            requests.get(url)
                            menu_principal(chat_id, job)
                        except:
                            pass
                    else:
                        denied_users = [user['name']['S']+' ('+user['user_id']['S']+')' for user in user_denied()]
                        buttons={}
                        buttons['keyboard']=[[]]
                        array = 0
                        count = 1
                            
                        for user in denied_users:
                            if count<=2:
                                buttons['keyboard'][array].append({'text':user})
                                count+=1
                                        
                            else:
                                buttons['keyboard'].append([])
                                count=1
                                array+=1
                                buttons['keyboard'][array].append({'text':user})
                                count+=1
                                    
                        buttons['keyboard'].append([])
                        array+=1
                        buttons['keyboard'][array].append({'text':'Voltar'})
                        
                        buttons['keyboard'].append([])
                        array+=1
                        buttons['keyboard'][array].append({'text':'Sair'})
                                    
                        buttons['resize_keyboard']=True
                        buttons['one_time_keyboard']=True
                        buttons['selective']=True
                                
                        reply_kb_markup = json.dumps(buttons, indent = 4)
                                
                        final_text="Selecione o usuário"
                        url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
                        requests.get(url)

                elif (action[3].lower() == 'excluir'):
                    userId = action[2][(action[2].index('(')+1):-1]
                    response = user_exists(userId)
                    keys = list([key for key in response.keys()])
                    if 'Item' in keys:
                        user = response['Item']
                        try:
                            user_delete(user)
                            date_hour = datetime.now()
                            response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
                            final_text="Usuário excluído com sucesso"
                            url = URL + "sendMessage?text={}&chat_id={}".format(final_text,chat_id)
                            requests.get(url)
                            menu_principal(chat_id, job)
                        except:
                            pass
                    else:
                        denied_users = [user['name']['S']+' ('+user['user_id']['S']+')' for user in user_denied()]
                        buttons={}
                        buttons['keyboard']=[[]]
                        array = 0
                        count = 1
                            
                        for user in denied_users:
                            if count<=2:
                                buttons['keyboard'][array].append({'text':user})
                                count+=1
                                        
                            else:
                                buttons['keyboard'].append([])
                                count=1
                                array+=1
                                buttons['keyboard'][array].append({'text':user})
                                count+=1
                                    
                        buttons['keyboard'].append([])
                        array+=1
                        buttons['keyboard'][array].append({'text':'Voltar'})
                        
                        buttons['keyboard'].append([])
                        array+=1
                        buttons['keyboard'][array].append({'text':'Sair'})
                                    
                        buttons['resize_keyboard']=True
                        buttons['one_time_keyboard']=True
                        buttons['selective']=True
                                
                        reply_kb_markup = json.dumps(buttons, indent = 4)
                                
                        final_text="Selecione o usuário"
                        url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
                        requests.get(url)
        
            else:
                buttons={}
                array=0
                buttons['keyboard']=[[]]
                buttons['keyboard'][array].append({'text':'Liberar'})
                buttons['keyboard'][array].append({'text':'Excluir'})
                buttons['keyboard'].append([])
                array+=1
                buttons['keyboard'][array].append({'text':'Voltar'})
                buttons['keyboard'].append([])
                array+=1
                buttons['keyboard'][array].append({'text':'Sair'})
                            
                buttons['resize_keyboard']=True
                buttons['one_time_keyboard']=True
                buttons['selective']=True
                        
                reply_kb_markup = json.dumps(buttons, indent = 4)
                        
                final_text="Selecione uma opção"
                url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
                requests.get(url)
                
        else:
            buttons={}
            buttons['keyboard']=[[]]
            array = 0
            count = 1
                
            for user in denied_users:
                if count<=2:
                    buttons['keyboard'][array].append({'text':user})
                    count+=1
                            
                else:
                    buttons['keyboard'].append([])
                    count=1
                    array+=1
                    buttons['keyboard'][array].append({'text':user})
                    count+=1
                        
            buttons['keyboard'].append([])
            array+=1
            buttons['keyboard'][array].append({'text':'Voltar'})
            
            buttons['keyboard'].append([])
            array+=1
            buttons['keyboard'][array].append({'text':'Sair'})
                        
            buttons['resize_keyboard']=True
            buttons['one_time_keyboard']=True
            buttons['selective']=True
                    
            reply_kb_markup = json.dumps(buttons, indent = 4)
                    
            final_text="Selecione o usuário"
            url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
            requests.get(url)
    
    elif (len(action)==2) and action[0].lower() == 'usuários' and action[1].lower()=='bloquear':
        allowed_users = [user['name']['S']+' ('+user['user_id']['S']+')' for user in user_allowed() if user['job']['S'] != 'Adm']
        buttons={}
        buttons['keyboard']=[[]]
        array = 0
        count = 1
            
        for user in allowed_users:
            if count<=2:
                buttons['keyboard'][array].append({'text':user})
                count+=1
                        
            else:
                buttons['keyboard'].append([])
                count=1
                array+=1
                buttons['keyboard'][array].append({'text':user})
                count+=1
                    
        buttons['keyboard'].append([])
        array+=1
        buttons['keyboard'][array].append({'text':'Voltar'})
        
        buttons['keyboard'].append([])
        array+=1
        buttons['keyboard'][array].append({'text':'Sair'})
                    
        buttons['resize_keyboard']=True
        buttons['one_time_keyboard']=True
        buttons['selective']=True
                
        reply_kb_markup = json.dumps(buttons, indent = 4)
                
        final_text="Selecione o usuário"
        url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
        requests.get(url)
        
        date_hour = datetime.now()
        response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
        
    elif (len(action)==3  and action[0].lower() == 'usuários' and action[1].lower()=='bloquear'):
        allowed_users = [user['name']['S']+' ('+user['user_id']['S']+')' for user in user_allowed() if user['job']['S'] != 'Adm']
        if (action[2] in allowed_users):
            buttons={}
            array=0
            buttons['keyboard']=[[]]
            buttons['keyboard'][array].append({'text':'Bloquear'})
            buttons['keyboard'][array].append({'text':'Excluir'})
            buttons['keyboard'].append([])
            array+=1
            buttons['keyboard'][array].append({'text':'Voltar'})
            buttons['keyboard'].append([])
            array+=1
            buttons['keyboard'][array].append({'text':'Sair'})
                        
            buttons['resize_keyboard']=True
            buttons['one_time_keyboard']=True
            buttons['selective']=True
                    
            reply_kb_markup = json.dumps(buttons, indent = 4)
                    
            final_text="Selecione uma opção"
            url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
            requests.get(url)
            
            date_hour = datetime.now()
            response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
        else:
            buttons={}
            buttons['keyboard']=[[]]
            array = 0
            count = 1
                
            for user in allowed_users:
                if count<=2:
                    buttons['keyboard'][array].append({'text':user})
                    count+=1
                            
                else:
                    buttons['keyboard'].append([])
                    count=1
                    array+=1
                    buttons['keyboard'][array].append({'text':user})
                    count+=1
                        
            buttons['keyboard'].append([])
            array+=1
            buttons['keyboard'][array].append({'text':'Voltar'})
            
            buttons['keyboard'].append([])
            array+=1
            buttons['keyboard'][array].append({'text':'Sair'})
                        
            buttons['resize_keyboard']=True
            buttons['one_time_keyboard']=True
            buttons['selective']=True
                    
            reply_kb_markup = json.dumps(buttons, indent = 4)
                    
            final_text="Selecione o usuário"
            url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
            requests.get(url)
    
    elif (len(action)==4 and action[0].lower() == 'usuários' and action[1].lower()=='bloquear'):
        allowed_users = [user['name']['S']+' ('+user['user_id']['S']+')' for user in user_allowed() if user['job']['S'] != 'Adm']
        
        if (action[2] in allowed_users):
            
            if (action[3].lower() in ('bloquear','excluir')):
                
                if (action[3].lower() == 'bloquear'):
                    userId = action[2][(action[2].index('(')+1):-1]
                    response = user_exists(userId)
                    keys = list([key for key in response.keys()])
                    if 'Item' in keys:
                        user = response['Item']
                        try:
                            deny_user(user)
                            date_hour = datetime.now()
                            response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
                            final_text="Usuário bloqueado com sucesso"
                            url = URL + "sendMessage?text={}&chat_id={}".format(final_text,chat_id)
                            requests.get(url)
                            menu_principal(chat_id, job)
                        except:
                            pass
                    else:
                        allowed_users = [user['name']['S']+' ('+user['user_id']['S']+')' for user in user_allowed() if user['job']['S'] != 'Adm']
                        buttons={}
                        buttons['keyboard']=[[]]
                        array = 0
                        count = 1
                            
                        for user in allowed_users:
                            if count<=2:
                                buttons['keyboard'][array].append({'text':user})
                                count+=1
                                        
                            else:
                                buttons['keyboard'].append([])
                                count=1
                                array+=1
                                buttons['keyboard'][array].append({'text':user})
                                count+=1
                                    
                        buttons['keyboard'].append([])
                        array+=1
                        buttons['keyboard'][array].append({'text':'Voltar'})
                        
                        buttons['keyboard'].append([])
                        array+=1
                        buttons['keyboard'][array].append({'text':'Sair'})
                                    
                        buttons['resize_keyboard']=True
                        buttons['one_time_keyboard']=True
                        buttons['selective']=True
                                
                        reply_kb_markup = json.dumps(buttons, indent = 4)
                                
                        final_text="Selecione o usuário"
                        url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
                        requests.get(url)

                elif (action[3].lower() == 'excluir'):
                    userId = action[2][(action[2].index('(')+1):-1]
                    response = user_exists(userId)
                    keys = list([key for key in response.keys()])
                    if 'Item' in keys:
                        user = response['Item']
                        try:
                            user_delete(user)
                            date_hour = datetime.now()
                            response = session_update(chat_id, session_id, date_hour, commands, 'aberta')
                            final_text="Usuário excluído com sucesso"
                            url = URL + "sendMessage?text={}&chat_id={}".format(final_text,chat_id)
                            requests.get(url)
                            menu_principal(chat_id, job)
                        except:
                            pass
                    else:
                        allowed_users = [user['name']['S']+' ('+user['user_id']['S']+')' for user in user_allowed() if user['job']['S'] != 'Adm']
                        buttons={}
                        buttons['keyboard']=[[]]
                        array = 0
                        count = 1
                            
                        for user in allowed_users:
                            if count<=2:
                                buttons['keyboard'][array].append({'text':user})
                                count+=1
                                        
                            else:
                                buttons['keyboard'].append([])
                                count=1
                                array+=1
                                buttons['keyboard'][array].append({'text':user})
                                count+=1
                                    
                        buttons['keyboard'].append([])
                        array+=1
                        buttons['keyboard'][array].append({'text':'Voltar'})
                        
                        buttons['keyboard'].append([])
                        array+=1
                        buttons['keyboard'][array].append({'text':'Sair'})
                                    
                        buttons['resize_keyboard']=True
                        buttons['one_time_keyboard']=True
                        buttons['selective']=True
                                
                        reply_kb_markup = json.dumps(buttons, indent = 4)
                                
                        final_text="Selecione o usuário"
                        url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
                        requests.get(url)
        
            else:
                buttons={}
                array=0
                buttons['keyboard']=[[]]
                buttons['keyboard'][array].append({'text':'Liberar'})
                buttons['keyboard'][array].append({'text':'Excluir'})
                buttons['keyboard'].append([])
                array+=1
                buttons['keyboard'][array].append({'text':'Voltar'})
                buttons['keyboard'].append([])
                array+=1
                buttons['keyboard'][array].append({'text':'Sair'})
                            
                buttons['resize_keyboard']=True
                buttons['one_time_keyboard']=True
                buttons['selective']=True
                        
                reply_kb_markup = json.dumps(buttons, indent = 4)
                        
                final_text="Selecione uma opção"
                url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
                requests.get(url)
                
        else:
            allowed_users = [user['name']['S']+' ('+user['user_id']['S']+')' for user in user_allowed() if user['job']['S'] != 'Adm']
            buttons={}
            buttons['keyboard']=[[]]
            array = 0
            count = 1
                            
            for user in allowed_users:
                if count<=2:
                    buttons['keyboard'][array].append({'text':user})
                    count+=1
                            
                else:
                    buttons['keyboard'].append([])
                    count=1
                    array+=1
                    buttons['keyboard'][array].append({'text':user})
                    count+=1
                                    
            buttons['keyboard'].append([])
            array+=1
            buttons['keyboard'][array].append({'text':'Voltar'})
                    
            buttons['keyboard'].append([])
            array+=1
            buttons['keyboard'][array].append({'text':'Sair'})
                                    
            buttons['resize_keyboard']=True
            buttons['one_time_keyboard']=True
            buttons['selective']=True
                                
            reply_kb_markup = json.dumps(buttons, indent = 4)
                                
            final_text="Selecione o usuário"
            url = URL + "sendMessage?text={}&chat_id={}&reply_markup={}".format(final_text,chat_id,reply_kb_markup)
            requests.get(url)
        
        
        

    
