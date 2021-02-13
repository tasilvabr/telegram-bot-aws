import json
import os
import logging
import boto3
from botocore.vendored import requests

# Initializing a logger and settign it to INFO
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Reading environment variables and generating a Telegram Bot API URL
TOKEN = os.environ['TOKEN']
USER_ID = os.environ['USER_ID']
TELEGRAM_URL = "https://api.telegram.org/bot{}/sendMessage".format(TOKEN)

# Helper function to prettify the message if it's in JSON
def process_message(input):
    try:
        # Loading JSON into a string
        raw_json = json.loads(input)
        # Outputing as JSON with indents
        output = raw_json
    except:
        output = input
    return output

# Main Lambda handler
def lambda_handler(event, context):
    # logging the event for debugging
    logger.info("event=")
    logger.info(json.dumps(event))

    # Basic exception handling. If anything goes wrong, logging the exception    
    try:
        # Reading the message "Message" field from the SNS message
        message = process_message(event['Records'][0]['Sns']['Message'])
        
        try:
            instance_id = message['detail']['instance-id']
            state = message['detail']['state']
            
            ec2 = boto3.resource('ec2')
            for instance in ec2.instances.all():
                if (str(instance.id) == str(instance_id)):
                    instance_name = instance.tags[0]['Value']
                    break
            
            if (state == 'pending'):
                state_instance = "iniciando"
            elif (state == 'running'):
                state_instance = "ligada"
            elif (state == 'stopping'):
                state_instance = "desligando"
            elif (state == 'stopped'):
                state_instance = "desligada"
            elif (state == 'shutting-down'):
                state_instance = "encerrando"
            elif (state == 'terminated'):
                state_instance = "encerrada"
            else:
                state_instance = "desconhecido"
            
            message_send="A Instância {} está {}".format(instance_name,state_instance)
        
        except:
            message_send = str(message)


        # Payload to be set via POST method to Telegram Bot API
        payload = {
            "text": message_send.encode("utf8"),
            "chat_id": USER_ID
        }

        # Posting the payload to Telegram Bot API
        requests.post(TELEGRAM_URL, payload)

    except Exception as e:
        raise e
