from .settings_base import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'k2#@_q=1$(__n7#(zax6#46fu)x=3&^lz&bwb8ol-_097k_rj5'

# CyberSource creds
CS_ACCESS_KEY = 'test'
CS_PROFILE_ID = 'test'
CS_SECRET_KEY = 'a-really-long-test-string'
CS_PAYMENT_URL = 'https://testsecureacceptance.cybersource.com/pay'

# Our encryption key for storing full responses from CyberSource
# generated using perma_payments.security.generate_public_private_keys
# SECURITY WARNING: keep the production app secret key secret!
# SECURITY WARNING: keep the production vault secret key offline!
STORAGE_ENCRYPTION_KEYS = {
    'id': 3,
    'app_secret_key': b'\xf8O\xbe\x18Y\xd0f\xd0\xe1\xcc\xd1\x07\xc9\xdd\x18]p\xc9\xae\xfd\xe6\x91\xf6\xf76\x8ae\x84\x991\xad\x9e',
    'vault_secret_key': b'\x13.\xe1\x11\x88\x0b"D\x83\xbf\x1c0\xfd\xd0\x19\xa8\x8f{\x80\xfd\x85\xc4!\xc9o\x13\xb0\x96\xf8Y\xa7\xd6',
    'app_public_key': b'V\xbc\xc4>\x00\x99\x93\x14\xe1E\x0c]\xfc\x1e\xaf\xb4|s\xec\xee\xfcG\xd6\xae?^E\xee\xe3Zp2',
    'vault_public_key': b'\xbd6\xe14\x8dB\xb5\xac\xdb\x95\xdc.:=xhb\xbd\xacwx\xd5\x17G\x8a/\xa9\xf58\x9bpU',
}


# Encryption keys for communicating with Perma.cc
# generated using perma_payments.security.generate_public_private_keys
# SECURITY WARNING: keep the production secret key secret!
PERMA_ENCRYPTION_KEYS = {
    'id': 3,
    'perma_payments_secret_key': b'7\xe6#\xef\x08\xe4\xab\xc1#i\xcc\xb4\xb9\x02|\x17\xe4\x8c\xd7\x0e\x14nW\x96q\xbc\x99\xb5\xf13\x18A',
    'perma_payments_public_key': b'\x0co(\xf5\xc4\xb9.\x07\xae\xbb\xb5\xc0\x17O,\xc3F\x8e_\xb9\x89\x16\xefSTK]\xae\xb0P\x1c6',
    'perma_public_key': b'fi\x16S\xa0\x1dBSk\x0c"\xcd#^x\x1d!\x87\xf7\xa8\xe3\xb3mT\x03r\xbeb\x9a\x9e\xcdh',
}
PERMA_TIMESTAMP_MAX_AGE_SECONDS = 120
