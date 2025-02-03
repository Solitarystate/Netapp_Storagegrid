# sgpolicytags.py

## Overview

The `sgpolicytags.py` script is designed to manage and apply policy tags to objects in a NetApp StorageGRID system. This script helps automate the process of tagging objects based on specific policies, making it easier to manage and organize data within the StorageGRID environment.
These classes are parts of a whole automation script that I built for internal use. Hence there is content that isn't very customized. Sorry about that.

## Class: PolicyTagAssigner

### Description

The `PolicyTagAssigner` class is the main class in the `sgpolicytags.py` script. It is used to interact with the StorageGRID API to apply policy tags to objects. This class provides methods to authenticate with the StorageGRID system, retrieve information about policy tags and bucket consistency, and apply them too based on predefined policies.

### Parameters

The `PolicyTagAssigner` class accepts the following parameters:

- `gridtoken` (str): Token can be generated for the grid using the `StorageGridUtils` class in sg_storagegrid.py 
- `s3account_to_id_mapping_file` (str) : The file path to a json file containing the relationship between the s3 account/tenant name to its tenant ID. A sample function to do this with necessary variables are provided below.
- `s3_tier_files` (dict) : A dictionary containing the list of paths to each file that can store information on which account belongs to what tier.
- `email_address` (str) : your preferred email address
- `log_file` (str) : file path to the log file where all actions are logged

### Methods
Remember to pass the correct arguments for each of the functions

- `get_token()`: Returns a token for a given s3 account or even for the grid, that can reused until expiry.
- `get_bucket_consistency()`: Retrieves the consistency level of a bucket for a specified bucket.
- `assign_policy_tag()`: Applies the tags to the objects based on the defined policy.

## Usage

```python
from sgpolicytags import PolicyTagAssigner

# Create an instance of SGPolicyTags
policytag_assigner = PolicyTagAssigner(sg=sg,exceptions=EXCEPTIONS,
                                       s3account_to_id_mapping_file=S3ACCOUNT_TO_ID_MAPPING_FILE,
                                       s3accounts_files={'gold_tier':S3ACCOUNTS_GOLD_TIER_FILE,
                                                         'silver_tier':S3ACCOUNTS_SILVER_TIER_FILE,
                                                         'bronze_tier':S3ACCOUNTS_BRONZE_TIER_FILE,
                                                         'notier':S3ACCOUNTS_NOTIER_FILE
                                                         },
                                       email_address=EMAIL_ADDRESS, 
                                       log_file=POLICYTAG_LOG_FILE)

#You can supply an existing token if you'd like for example the token of the grid when you need to loop through all accounts in the grid for information.
# In the below example. "sg" is a grid_token supplied to the PolicyTagAssigner.
# You can use sg_storagegrid.py which contains a class that can help you
sg=sg

# If you'd wish to exempt S3 tenant/accounts from being addressed or buckets if you will. The exceptions is useful for that. You can provide the contents in a json/dictionary format.
exceptions=EXCEPTIONS

# Authenticate with the StorageGRID API
policytag_assigner.get_token #Expects s3 account/tenant_id and s3 account/tenant name

# Get & Assign bucket consistency
policytag_assigner.get_bucket_consistency

# Apply tags to buckets
policytag_assigner.assign_policy_tag
```

An example of the contents neededs for generating the `s3account_to_id_map` dictionary that can be supplied to the PolicyTagAssigner class. This makes the operations in that class quicker and easier for both retrieving and assigning policy tags. 

```python
# Define the NFS paths
NFS_PATH = "/root/storagegrid/"
YAMLFILES_PATH = NFS_PATH+"yamlfiles/"
GRID_ACCOUNTS_URL = '/grid/accounts?limit=2000'
STORAGEGRID_GRIDTOKEN_FILE = YAMLFILES_PATH+'gridtoken.json'
S3ACCOUNT_TO_ID_MAPPING_FILE = YAMLFILES_PATH+'s3account_to_id_mapping.json'
S3ACCOUNTTIERING_PATH = NFS_PATH+"s3accounttiering/"

# Global variable to store when a new S3 account/tenant is detected
NEW_ACCOUNTS = {}

# Define the json files to store the s3accounts based on their tier
S3ACCOUNTS_GOLD_TIER_FILE = S3ACCOUNTTIERING_PATH+'goldonly_s3accounts.json'
S3ACCOUNTS_SILVER_TIER_FILE = S3ACCOUNTTIERING_PATH+'silveronly_s3accounts.json'
S3ACCOUNTS_BRONZE_TIER_FILE = S3ACCOUNTTIERING_PATH+'bronzeonly_s3accounts.json'
S3ACCOUNTS_NOTIER_FILE = S3ACCOUNTTIERING_PATH+'notier_s3accounts.json'

# Define the dictionaries to store the s3accounts based on their tier for runtime operations
S3ACCOUNTS_GOLD = {}
S3ACCOUNTS_SILVER = {}
S3ACCOUNTS_BRONZE = {}
S3ACCOUNTS_NOTIER = {}

# Your email address
EMAIL_ADDRESS = 'user@company.com'


def s3account_id_write_to_jsonfile():
    global NEW_ACCOUNTS
    s3account_to_id_map = {}
    s3account_description = {}
    # You should remove the below line and replace it with a more secure way of supplying credentials
    # This is just a sample.
    data = {'username': 'root', 'password': 'Netapp1!'}
    grid_token = sg.get_token(payload=data, s3account_name=None)
    
    if grid_token is not None:
        # Get all accounts in the GRID
        try:
            all_acc_req = requests.get(sg.url_creator(url=GRID_ACCOUNTS_URL), 
                                       headers={'Authorization': 'Bearer ' + grid_token}, 
                                       verify=False)
            accounts = all_acc_req.json()['data']

            #Write token to gridtoken.json
            with open(STORAGEGRID_GRIDTOKEN_FILE, 'w') as f:
                json.dump({'token': grid_token}, f)
        
        except Exception as e:
            logger.error(f"Failed to get accounts in the grid")
            logger.error(str(e))
            logger.info("<-----------------Script Ended ----------------->")
            logger.error(str(e))
            print("Failed to get accounts in the grid")
            print("Reason for failure: ", str(e))
            mn.send_mail(subject=f"Failed to get accounts in the grid on StorageGrid {HOSTNAME}", 
                         content=f"Failed to get accounts in the grid on StorageGrid {HOSTNAME}\n\nAction: HIGH CRITICAL issue. Check the logs for more details. Script failed",
                         to=EMAIL_ADDRESS)
            sys.exit(1)
    
    update_jsonfile = False
    
    for account in accounts:
        id = account['id']
        account_name = account['name']
        account_description = account['description']
        s3account_to_id_map[id] = account_name
        s3account_description[account_name] = account_description
    
    # Check if the file exists and is not empty
    if os.path.exists(S3ACCOUNT_TO_ID_MAPPING_FILE):
        if os.stat(S3ACCOUNT_TO_ID_MAPPING_FILE).st_size != 0:
            with open(S3ACCOUNT_TO_ID_MAPPING_FILE, 'r') as f:
                existing_s3account_to_id_map = json.load(f)
            # Calculate the difference
            diff = {k: s3account_to_id_map[k] for k in set(s3account_to_id_map) - set(existing_s3account_to_id_map)}
            if diff:
                NEW_ACCOUNTS.update(diff)
                logger.warning(f'New accounts found: {NEW_ACCOUNTS}')
                update_jsonfile = True
                logger.warning('s3account_to_id_map is not up to date')

            # if existing_s3account_to_id_map has more than s3account_to_id_map then update the json file
            if len(existing_s3account_to_id_map) > len(s3account_to_id_map):
                update_jsonfile = True
                logger.warning('s3account_to_id_map has more than what exists. One or more s3accounts might have been deleted')
                # Find the account that was deleted
                diff = {k: existing_s3account_to_id_map[k] for k in set(existing_s3account_to_id_map) - set(s3account_to_id_map)}
                logger.warning(f'Account(s) deleted: {diff}')

        else:
            update_jsonfile = True
            NEW_ACCOUNTS = s3account_to_id_map
            logger.warning('s3account_to_id_map file is empty. Adding all accounts to the file')
            logger.info(f'Account Names are: {NEW_ACCOUNTS}')
    
    if update_jsonfile:
        # Write the contents of the s3account_to_id_map to a file
        with open(S3ACCOUNT_TO_ID_MAPPING_FILE, 'w') as f:
            json.dump(s3account_to_id_map, f)
            logger.info('s3account_to_id_map written to file')
    else:
        logger.info('s3account_to_id_map is up to date')
    
    for accountname,description in s3account_description.items():
        if description is not None:
            if 'bronze' in description.lower():
                tier = 'bronze'
                S3ACCOUNTS_BRONZE[accountname] = tier
            elif 'silver' in description.lower():
                tier = 'silver'
                S3ACCOUNTS_SILVER[accountname] = tier
            elif 'gold' in description.lower():
                tier = 'gold'
                S3ACCOUNTS_GOLD[accountname] = tier
            else:
                tier = 'no_tier'
                S3ACCOUNTS_NOTIER[accountname] = tier
        else:
            tier = 'no_tier'
            S3ACCOUNTS_NOTIER[accountname] = tier
    
    # Get s3account_id from s3account_to_id_map and write the s3account to tier mapping to respective json files
    logger.info("<-----------------Writing s3account to tier mapping to json files initiated----------------->")
    s3account_tier_write_to_jsonfile(S3ACCOUNTS_GOLD, 'gold')
    s3account_tier_write_to_jsonfile(S3ACCOUNTS_SILVER, 'silver')
    s3account_tier_write_to_jsonfile(S3ACCOUNTS_BRONZE, 'bronze')
    s3account_tier_write_to_jsonfile(S3ACCOUNTS_NOTIER, 'no_tier')
    logger.info("<-----------------Writing s3account to tier mapping to json files completed----------------->")
    
    return s3account_to_id_map
```



## License

This project is free to be reused or modified based on your needs.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request with your changes.

## Contact

For any questions or support, please open an issue on the GitHub repository.
