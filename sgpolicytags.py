#/bin/python3
# -*- coding: utf-8 -*-
# Author: Sudeesh Varier
# Date: 2024-01-08
# Version: 1.0

import os
import json
import logging
import mailnotification as mn
import requests

####################
# GLOBAL VARIABLES #
####################

# GET AND PUT REQUESTS
bucket_policy_tag_url = "/org/containers/{}/ilm-policy-tag"
bucket_consistency_url = "/org/containers/{}/consistency"
create_access_key_url = "/org/users/current-user/s3-access-keys"
check_current_user_accesskey = "/org/users/current-user/s3-access-keys"
list_buckets_url = "/org/containers?include=compliance,region"

# Below is a class that contains several methods that are reusable across scripts if needed to deal with StorageGrid policy tags

class PolicyTagAssigner:
    def __init__(self, sg, exceptions, s3account_to_id_mapping_file, s3accounts_files, email_address, log_file):
        self.sg = sg
        self.exceptions = exceptions
        self.s3account_to_id_mapping_file = s3account_to_id_mapping_file
        self.s3accounts_files = s3accounts_files
        self.s3account_to_id_map = {}
        self.email_address = email_address
        self.goldonly_s3accounts = []
        self.silveronly_s3accounts = []
        self.bronzeonly_s3accounts = []
        self.notier_s3accounts = []
        self.gold_buckets = []
        self.silver_buckets = []
        self.bronze_buckets = []
        self.buckets_failed_policytag_assignment = []
        self.buckets_failed_consistency_assignment = []
        self.default_policytag_buckets = {}
        
        # Configure the logger for this class
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        
        # Create file handler which logs even debug messages
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        
        # Create console handler with a higher log level
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        
        # Create formatter and add it to the handlers
        formatter = logging.Formatter("[%(asctime)s] %(filename)s in %(funcName)s(), line %(lineno)d (%(levelname)s): %(message)s", datefmt='%Y-%m-%d %H:%M:%S')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        # Add the handlers to the logger
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
    
    def get_bucket_list(self, s3account:str, token:str):
        bucket_list = []
        try:
            bucket_list_output = requests.get(self.sg.url_creator(url=list_buckets_url), 
                                    headers={'Authorization': 'Bearer ' + token}, 
                                    verify=False)
            
            if 'data' in bucket_list_output.json() and len(bucket_list_output.json()['data']) > 0:
                for each_bucket in bucket_list_output.json()['data']:
                    if each_bucket['name'] not in self.exceptions['buckets']:
                        bucket_list.append(each_bucket['name'])
                    else:
                        self.logger.warning(f"Skipping the bucket '{each_bucket['name']}' as it is in the exceptions list")
            else:
                self.logger.warning("No buckets found in the s3account")
    
        except Exception as e:
            error = f"Unable to get the list of buckets for {s3account}. Error:{e}"
            self.logger.error(error)
            print(error)
        return bucket_list
    
    def get_bucket_policy_tag(self, bucketname:str, token:str):
        bucket_policytag = {}
        try:
            response = requests.get(self.sg.url_creator(url=bucket_policy_tag_url.format(bucketname)), 
                                    headers={'Authorization': 'Bearer ' + token}, 
                                    verify=False)
            
            if 'data' in response.json() and len(response.json()['data']) > 0:
                if 'ilmPolicyTagName' in response.json()['data']:
                    bucket_policytag[bucketname] = response.json()['data']['ilmPolicyTagName']
                else:
                    self.logger.error(f"No policy tag found for the bucket {bucketname}")
            else:
                self.logger.error(f"No policy tag found for the bucket {bucketname}")
        
        except Exception as e:
            error = f"Unable to get the policy tag for the bucket {bucketname}. Error:{e}"
            self.logger.error(error)
            print(error)
        
        return bucket_policytag
    
    def assign_bucket_policy_tag(self, s3account:str, bucketname:str, tagname:str, token:str):
        payload = {'ilmPolicyTagName': tagname}
        status = None
        try:
            response = requests.put(self.sg.url_creator(url=bucket_policy_tag_url.format(bucketname)), 
                                    data=json.dumps(payload), 
                                    headers={'Authorization': 'Bearer ' + token}, 
                                    verify=False)
        
            if 'data' in response.json() and len(response.json()['data']) > 0:
                self.logger.info(f"Policy tag {tagname} assigned to the bucket {bucketname} in {s3account}")
                status = response.json()['status']
            else:
                self.logger.error(f"Unable to assign the policy tag {tagname} to the bucket '{bucketname}' in s3account '{s3account}'")
                status = response.json()['status']
        
        except Exception as e:
            error = f"Unable to assign the policy tag {tagname} to the bucket '{bucketname}' in s3account '{s3account}'. Error:{e}"
            self.logger.error(error)
            print(error)
        
        return status
    
    def get_bucket_consistency(self, s3account:str, bucketname:str, token:str):
        bucket_consistencylevel = {}
        try:
            response = requests.get(self.sg.url_creator(url=bucket_consistency_url.format(bucketname)), 
                                    headers={'Authorization': 'Bearer ' + token}, 
                                    verify=False)
            
            if 'data' in response.json() and len(response.json()['data']) > 0:
                bucket_consistencylevel[bucketname] = response.json()['data']['consistency']
            else:
                self.logger.error(f"No consistency level found for the bucket '{bucketname}' in s3account '{s3account}'")
                
        except Exception as e:
            error = f"Unable to get the consistency level for the bucket '{bucketname}' in s3account '{s3account}'. Error:{e}"
            self.logger.error(error)
            print(error)
        
        return bucket_consistencylevel
    
    def assign_bucket_consistency(self, consistency:str, token:str):
        payload = {'consistency': consistency}
        response = requests.post(self.sg.url_creator(url=bucket_consistency_url), 
                                data=json.dumps(payload), 
                                headers={'Authorization': 'Bearer ' + token}, 
                                verify=False)
        return response.json()['status']
    
    def get_token(self, s3account_id, s3account_name):
        credentials = {'s3console_username': 'root', 's3console_password': 'Netapp1!'}  # for testing only. remove in production
        payload = {
            "accountId": s3account_id,
            "username": credentials['s3console_username'],
            "password": credentials['s3console_password'],
            "cookie": True,
            "csrfToken": False
        }
        return self.sg.get_token(payload, s3account_name)
    
    def load_s3account_to_id_map(self):
        if os.path.exists(self.s3account_to_id_mapping_file):
            if os.stat(self.s3account_to_id_mapping_file).st_size != 0:
                with open(self.s3account_to_id_mapping_file, 'r') as f:
                    self.s3account_to_id_map = json.load(f)
            else:
                raise Exception("The s3account to id mapping file is empty")
        else:
            raise Exception("The s3account to id mapping file does not exist")
    
    def load_s3accounts(self):
        with open(self.s3accounts_files['gold_tier'], 'r') as f:
            self.goldonly_s3accounts = json.load(f)
        with open(self.s3accounts_files['silver_tier'], 'r') as f:
            self.silveronly_s3accounts = json.load(f)
        with open(self.s3accounts_files['bronze_tier'], 'r') as f:
            self.bronzeonly_s3accounts = json.load(f)
        with open(self.s3accounts_files['notier'], 'r') as f:
            self.notier_s3accounts = json.load(f)
    
    def remove_exceptions(self):
        self.s3account_to_id_map = {k: v for k, v in self.s3account_to_id_map.items() if v not in self.exceptions['accounts']}
        self.logger.info("Cleaned up the exceptions from the s3account to id mapping file")
    
    def process_s3accounts(self):
        for s3account_id, s3account_name in self.s3account_to_id_map.items():
            self.logger.info(f"Processing s3account: {s3account_name}")
            print(f"Processing s3account: {s3account_name}")
            token = self.get_token(s3account_id, s3account_name)
            bucket_list = self.get_bucket_list(s3account_name, token)
            self.process_buckets(s3account_name, bucket_list, token)
    
    def process_buckets(self, s3account_name, bucket_list, token):
        if len(bucket_list) > 0:
            for bucket in bucket_list:
                bucket_policytag = self.get_bucket_policy_tag(bucketname=bucket, token=token)
                bucket_consistency = self.get_bucket_consistency(s3account=s3account_name, bucketname=bucket, token=token)
                self.assign_policy_tag(s3account_name, bucket, bucket_policytag, token)
                new_consistency = self.get_bucket_consistency(s3account=s3account_name, bucketname=bucket, token=token)
                if new_consistency[bucket] != bucket_consistency[bucket]:
                    self.assign_bucket_consistency(consistency=bucket_consistency[bucket], token=token)
                    self.buckets_failed_consistency_assignment.append(f"{bucket}-{s3account_name}")
                else:
                    self.logger.info(f"Consistency level for the bucket '{bucket}' in s3account '{s3account_name}' is unchanged after the policy tag assignment or verification")
                    self.logger.info(f"Consistency level for {bucket}: {bucket_consistency[bucket]}")
        else:
            self.logger.warning(f"No buckets found in the s3account '{s3account_name}'")
    
    def assign_policy_tag(self, s3account_name, bucket, bucket_policytag, token):
        if len(bucket_policytag) > 0:
            if s3account_name in self.goldonly_s3accounts and bucket_policytag[bucket] != 'Gold':
                self.logger.info(f"INCORRECT-POLICYTAG-FOUND: Assigning Gold policy tag to the bucket '{bucket}' in s3account '{s3account_name}'")
                self.assign_tag(s3account_name, bucket, 'Gold', token)
            elif s3account_name in self.silveronly_s3accounts and bucket_policytag[bucket] != 'Silver':
                self.logger.info(f"INCORRECT-POLICYTAG-FOUND: Assigning Silver policy tag to the bucket '{bucket}' in s3account '{s3account_name}'")
                self.assign_tag(s3account_name, bucket, 'Silver', token)
            elif s3account_name in self.bronzeonly_s3accounts and bucket_policytag[bucket] != 'Bronze':
                self.logger.info(f"INCORRECT-POLICYTAG-FOUND: Assigning Bronze policy tag to the bucket '{bucket}' in s3account '{s3account_name}'")
                self.assign_tag(s3account_name, bucket, 'Bronze', token)
            elif s3account_name in self.notier_s3accounts and bucket_policytag[bucket] is None:
                self.logger.error(f"ALERT!: bucket '{bucket}' in s3account '{s3account_name}' is assigned to default policy tag")
                # Ensure the s3account_name key exists in the dictionary and append the bucket to the list
                if s3account_name not in self.default_policytag_buckets:
                    self.default_policytag_buckets[s3account_name] = []
                self.default_policytag_buckets[s3account_name].append(bucket)
            elif s3account_name in self.goldonly_s3accounts and bucket_policytag[bucket] == 'Gold':
                self.gold_buckets.append(bucket)
                self.logger.info(f"Gold policy tag found for the bucket '{bucket}' in s3account '{s3account_name}'")
            elif s3account_name in self.silveronly_s3accounts and bucket_policytag[bucket] == 'Silver':
                self.silver_buckets.append(bucket)
                self.logger.info(f"Silver policy tag found for the bucket '{bucket}' in s3account '{s3account_name}'")
            elif s3account_name in self.bronzeonly_s3accounts and bucket_policytag[bucket] == 'Bronze':
                self.bronze_buckets.append(bucket)
                self.logger.info(f"Bronze policy tag found for the bucket '{bucket}' in s3account '{s3account_name}'")
            elif s3account_name in self.notier_s3accounts and bucket_policytag[bucket] == 'Gold':
                self.gold_buckets.append(bucket)
                self.logger.info(f"Gold policy tag found for the bucket '{bucket}' in s3account '{s3account_name}'")
            elif s3account_name in self.notier_s3accounts and bucket_policytag[bucket] == 'Silver':
                self.silver_buckets.append(bucket)
                self.logger.info(f"Silver policy tag found for the bucket '{bucket}' in s3account '{s3account_name}'")
            elif s3account_name in self.notier_s3accounts and bucket_policytag[bucket] == 'Bronze':
                self.bronze_buckets.append(bucket)
                self.logger.info(f"Bronze policy tag found for the bucket '{bucket}' in s3account '{s3account_name}'")
            else:
                self.logger.info(f"Unknown policy tag found for the bucket '{bucket}' in s3account '{s3account_name}'")
    
    def assign_tag(self, s3account_name, bucket, tagname, token):
        assign_status = self.assign_bucket_policy_tag(s3account=s3account_name, bucketname=bucket, tagname=tagname, token=token)
        if assign_status.lower() != 'success':
            self.logger.error(f"Failed to assign the policytag '{tagname}' to the bucket '{bucket}' in s3account '{s3account_name}'")
            self.buckets_failed_policytag_assignment.append(f"{s3account_name}-{bucket}-{tagname}")
    
    def send_email(self):
        if len(self.buckets_failed_policytag_assignment) > 0:
            self.logger.error(f"Bucket Policy Tag Assignment Failed for: {self.buckets_failed_policytag_assignment}")
            email_subject = "Policy Tag Assignment Failed"
            email_body = f"The following buckets failed to get the policy tag assigned:\n\n"
            email_body += "*s3accountname-bucket_name-tagname*\n================================\n"
            for bucket in self.buckets_failed_policytag_assignment:
                email_body += f"{bucket}\n"
            mn.send_mail(email_subject, email_body, self.email_address)
            self.logger.info("Sent email notification for failed policy tag assignment")
        if len(self.buckets_failed_consistency_assignment) > 0:
            self.logger.error(f"Bucket Consistency Assignment Failed for: {self.buckets_failed_consistency_assignment}")
            email_subject = "Consistency Assignment Failed"
            email_body = f"The following buckets failed to get the consistency level assigned:\n\n"
            for bucket in self.buckets_failed_consistency_assignment:
                email_body += f"{bucket}\n"
            mn.send_mail(email_subject, email_body, self.email_address)
            self.logger.info("Sent email notification for failed consistency assignment")
        if len(self.default_policytag_buckets) > 0:
            self.logger.error(f"Buckets assigned to the default policy tag: {self.default_policytag_buckets}")
            email_subject = "Default Policy Tag Assignment"
            email_body = f"The following buckets are assigned to the default policy tag:\n\n"
            email_body += "*s3accountname -- bucket_names*\n====================\n"
            for s3account, bucket in self.default_policytag_buckets.items():
                email_body += f"{s3account} -- {bucket}\n"
            mn.send_mail(email_subject, email_body, self.email_address)
            self.logger.info("Sent email notification for default policy tag assignment")
    
    def run(self):
        self.logger.info("<================== Starting the Policy Tag Script ==================>")
        self.logger.info(f"Fetching the s3accounts from local file '{self.s3account_to_id_mapping_file}'")
        self.load_s3account_to_id_map()
        self.load_s3accounts()
        self.remove_exceptions()
        self.logger.info("Starting the policy tag assignment process for all s3accounts")
        self.process_s3accounts()
        self.logger.info("Policy tag assignment process completed for all s3accounts")
        self.send_email()
        self.logger.info("<================== Policy Tag Script Completed ==================>")