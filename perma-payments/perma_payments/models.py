from collections import Sequence
import random
from uuid import uuid4
from polymorphic.models import PolymorphicModel

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .security import encrypt_for_storage, stringify_request_post_for_encryption, nonce_from_pk

import logging
logger = logging.getLogger(__name__)

#
# CONSTANTS
#

RN_SET = "0123456789"
REFERENCE_NUMBER_PREFIX = "PERMA"
STANDING_STATUSES = ['Current', 'Hold']

#
# HELPERS
#


def generate_reference_number():
    """
    Generate a unique, human-friendly reference number. Based on Perma GUID generation.

    Only make 100 attempts:
    If there are frequent collisions, expand the keyspace or change the prefix.
    """
    for i in range(100):
        # Generating the reference number feels overly complex here. What about something like this?
        rn = "PERMA-{}-{}".format(
            "".join(random.choices(RN_SET, k=4)),
            "".join(random.choices(RN_SET, k=4))
        )

        rn = get_formatted_reference_number(random.choices(RN_SET, k=8), REFERENCE_NUMBER_PREFIX)
        if is_ref_number_available(rn):
            break
    else:
        raise Exception("No valid reference_number found in 100 attempts.")
    return rn


def get_formatted_reference_number(rn, prefix):
    """
    Given a sequence of non-hyphen characters, returns the formatted string (prefixed and with hyphens every 4 chars).
    E.g "12345678" -> "PERMA-1234-5678".
    E.g "12345" -> "PERMA-1-2345".
    """
    if not rn or not isinstance(rn, Sequence) or not all(isinstance(c, str) and len(c)==1 and c!='-'for c in rn):
        raise TypeError("Provide a sequence of non-hyphen characters")
    if not prefix or not isinstance(prefix, str) or '-' in prefix:
        raise TypeError("Provide a string with no hyphens.")

    # split reference number into 4-char chunks, starting from the end
    rn_parts = ["".join(rn[max(i - 4, 0):i]) for i in range(len(rn), 0, -4)]

    # stick together parts with '-'
    return "{}-{}".format(prefix, "-".join(reversed(rn_parts)))


def is_ref_number_available(rn):
    return not SubscriptionRequest.objects.filter(reference_number=rn).exists()


#
# CLASSES
#

# We might want to track history of this model rather than just keeping the latest status and update date.
# We use django-simple-history for this purpose in the perma codebase, although I don't have a strong feeling about what library is best.

# (Keeping a last update date in general strikes me as a nudge that you might want to track history -- if you care
# when it was last updated, you might also want to see what it was before.)

class SubscriptionAgreement(models.Model):
    """
    A Subscription Agreement comprises:
        a) A request to pay an amount, on a schedule, with a particular card and particular billing address
        b) CyberSource's initial response to the request.
           If CyberSource approves the subscription request,
           a 'Payment Token', also known as a 'Subscription ID', will be included in the response.
        c) Any subsequent updates from CyberSource about attempted scheduled payments
           associated with the Subscription ID. Indicates whether payments were successful and
           the agreement still stands.

    N.B. Perma-Payments does NOT support 16-digit format-preserving subscription IDs.

    If a CyberSource account is configured to use a 16-digit format-preserving Payment Token/Subscription ID,
    and if the customer subsequently updates the card number, CyberSource will mark the original Payment Token
    as obsolete ("superseded") and issue a new Payment Token/Subscription ID.

    Perma-Payments only supports unchanging, updateable Payment Tokens,
    which are the CyberSource default as of 8/16/17.

    Perma-Payments will log an error if any 16-digit Payment Tokens are received.
    """
    def __str__(self):
        return 'SubscriptionAgreement {}'.format(self.id)

    registrar = models.IntegerField()
    status = models.CharField(
        max_length=20,
        choices=(
            # Before we have received a definitive response from CyberSource
            ('Pending', 'Pending'),
            # CyberSource has rejected the request; no payment token/subscription ID was issued
            ('Rejected', 'Rejected'),
            # The user did not submit payment information
            ('Aborted', 'Aborted'),
            #
            # CyberSource approved the request and a payment token/subscription ID was issued
            # The subscription can lapse, etc. at any point thereafter.
            # CyberSource will report one of the below status values for each initially-approved subscription in the Business Center
            # from https://ebctest.cybersource.com/ebctest/help/en/index.html#page/Business_Center_Help/sub_search_results.htm
            #
            # The subscription has been canceled.
            ('Cancelled', 'Cancelled'),
            # All payments have been processed (installments subscriptions).
            # You see this status one or two days after the last payment is processed.
            # (As of 8/16/17, should never be returned to Perma Payments, since we are not selling installment plans.)
            ('Completed', 'Completed'),
            # The subscription is active, and the payments are up to date.
            ('Current', 'Current'),
            # The subscription is on hold because all payment attempts have failed
            # or a scheduled payment failed for a reason that requires your intervention.
            # You can see the subscriptions on hold in the daily Payment Exception Report.
            # For more information about holding profiles, see the Payment Tokenization documentation:
            # http://apps.cybersource.com/library/documentation/dev_guides/Payment_Tokenization/html
            ('Hold', 'Hold'),
            # The subscription has been updated and a new subscription ID has been assigned to it.
            # (As of 8/16/17, should never be returned to Perma Payments, since our account is not
            # configured to use 16-digit format-preserving payment tokens.)
            ('Superseded', 'Superseded')
        )
    )
    status_updated = models.DateTimeField(auto_now=True)
    cancellation_requested = models.BooleanField(
        default=False
    )


    @classmethod
    def registrar_standing_subscription(cls, registrar):
        # Nitpick -- I think this uses two sql queries to first check count() and then fetch the first one. I might do it as:
        #    standing = cls.objects.filter(...)[:2]
        # then you have a python list of 0 to 2 objects to work with
        standing = cls.objects.filter(registrar=registrar, status__in=STANDING_STATUSES)
        count = len(standing)
        if count == 0:
            return None
        if count > 1:
            logger.error("Registrar {} has multiple standing subscriptions ({})".format(registrar, count))
            if settings.RAISE_IF_MULTIPLE_SUBSCRIPTIONS_FOUND:
                raise cls.MultipleObjectsReturned

            # Maybe add a comment here to explain (in a few words) that we think it's OK to return the first subscription if multiple exist.

            # Also maybe add a sort order to this model (sort by id?), so we'll deterministically return the same object in this case --
            # nondeterminism can set folks up for bafflement in the future.
        return standing.first()


    def can_be_altered(self):
        return self.status in STANDING_STATUSES and not self.cancellation_requested


class OutgoingTransaction(PolymorphicModel):
    """
    Base model for all requests we send to CyberSource.
    """
    def __str__(self):
        return 'OutgoingTransaction {}'.format(self.id)

    transaction_uuid = models.UUIDField(
        default=uuid4,
        help_text="A unique ID for this 'transaction'. " +
                  "Intended to protect against duplicate transactions."
    )
    # Does "auto_now_add=True, null=True" make sense? Seems like it would never be null
    request_datetime = models.DateTimeField(auto_now_add=True, null=True)

    def get_formatted_datetime(self):
        """
        Returns the request_datetime in the format required by CyberSource
        """
        return self.request_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")


class SubscriptionRequest(OutgoingTransaction):
    """
    All (non-confidential) specifics of a customer's request for a subscription.

    Useful for:
    1) reconstructing a customer's account history;
    2) resending failed requests;
    3) comparing notes with CyberSource records
    """
    def __str__(self):
        return 'SubscriptionRequest {}'.format(self.id)

    subscription_agreement = models.OneToOneField(
        SubscriptionAgreement,
        related_name='subscription_request'
    )
    reference_number = models.CharField(
        max_length=32,
        default=generate_reference_number,
        help_text="Unqiue ID for this subscription. " +
                  "Subsequent charges, automatically made by CyberSource on the recurring schedule, " +
                  "will all be associated with this reference number. " +
                  "Called 'Merchant Reference Number' in CyberSource Business Center."
    )
    # N.B. the Cybersource test environment returns error codes for certain amounts, by design.
    # The docs are very unclear about the specifics.
    # Try to charge under $1,000 or over $10,000 when testing to avoid.
    amount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        help_text="Amount to be charged immediately"
    )
    recurring_amount = models.DecimalField(
        max_digits=19,
        decimal_places=2,
        help_text="Amount to be charged repeatedly, beginning on recurring_start_date"
    )
    recurring_start_date = models.DateField(
        help_text="Date on which to commence charging recurring_amount"
    )
    recurring_frequency = models.CharField(
        max_length=20,
        choices=(
            ('weekly', 'weekly'),  # every 7 days.
            ('bi-weekly', 'bi-weekly (every 2 weeks)'),  # every 2 weeks.
            ('quad-weekly', 'quad-weekly (every 4 weeks)'),  # every 4 weeks.
            ('monthly', 'monthly'),
            ('semi-monthly', 'semi-monthly (1st and 15th of each month)'),  # twice every month (1st and 15th).
            ('quarterly', 'quarterly'),
            ('semi-annually', 'semi-annually (twice every year)'),  # twice every year.
            ('annually', 'annually')
        )
    )
    currency = models.CharField(
        max_length=3,
        default='USD'
    )
    locale = models.CharField(
        max_length=5,
        default='en-us'
    )
    payment_method = models.CharField(
        max_length=30,
        default='card'
    )
    transaction_type = models.CharField(
        max_length=30,
        default='sale,create_payment_token'
    )

    @property
    def registrar(self):
        return self.subscription_agreement.registrar


    def get_formatted_start_date(self):
        """
        Returns the recurring_start_date in the format required by CyberSource
        """
        return self.recurring_start_date.strftime("%Y%m%d")


class UpdateRequest(OutgoingTransaction):
    """
    All (non-confidential) specifics of a customer's request to update their payment information.

    Useful for:
    1) reconstructing a customer's account history;
    2) resending failed requests;
    3) comparing notes with CyberSource records
    """
    def __str__(self):
        return 'UpdateRequest {}'.format(self.id)

    # related_name should be plural update_requests, right?
    subscription_agreement = models.ForeignKey(
        SubscriptionAgreement,
        related_name='update_request'
    )
    transaction_type = models.CharField(
        max_length=30,
        default='update_payment_token'
    )

    @property
    def registrar(self):
        return self.subscription_agreement.registrar


class Response(PolymorphicModel):
    """
    Base model for all responses we receive from CyberSource.

    Most fields are null, just in case CyberSource sends us something ill-formed.
    """
    def __str__(self):
        return 'Response {}'.format(self.id)

    def clean(self, *args, **kwargs):
        super(Response, self).clean(*args, **kwargs)
        if not self.full_response:
            raise ValidationError({'full_response': 'This field cannot be blank.'})


    # we can't guarantee cybersource will send us these fields, though we sure hope so
    decision = models.CharField(
        blank=True,
        null=True,
        max_length=7,
        choices=(
            ('ACCEPT', 'ACCEPT'),
            ('REVIEW', 'REVIEW'),
            ('DECLINE', 'DECLINE'),
            ('ERROR', 'ERROR'),
            ('CANCEL', 'CANCEL'),
        )
    )
    reason_code = models.IntegerField(blank=True, null=True)
    message = models.TextField(blank=True, null=True)
    # required
    full_response = models.BinaryField(
        help_text="The full response, encrypted, in case we ever need it."
    )
    encryption_key_id = models.IntegerField()

    @property
    def related_request(self):
        """
        Must be implemented by child models
        """
        raise NotImplementedError

    @property
    def subscription_agreement(self):
        """
        Must be implemented by child models
        """
        raise NotImplementedError

    @property
    def registrar(self):
        """
        Must be implemented by child models
        """
        raise NotImplementedError

    # typo in this method name -- encryped instead of encrypted. Also suggest "with" instead of "w"
    @classmethod
    def save_new_w_encryped_full_response(cls, response_class, full_response, fields):
        """
        Saves a new instance of type response_class, encrypting the
        'full_response' field
        """
        # Security issue: don't pass in a custom nonce here. This means that encrypt_for_storage() is insecure to use for anything *except*
        # one message per OutgoingTransaction, which is an easy-to-mess-up API. Just let pynacl generate the nonce.
        data = {
            'encryption_key_id': settings.STORAGE_ENCRYPTION_KEYS['id'],
            'full_response': encrypt_for_storage(
                stringify_request_post_for_encryption(full_response),
                # use the OutgoingTransaction pk as the nonce, to ensure uniqueness
                nonce_from_pk(fields['related_request'])
            )
        }
        data.update(fields)
        response = response_class(**data)
        # I'm not sure it makes sense to validate before saving here.
        # If there's some problem, what do we want to do?
        # Might as well just wait for any db integrity errors, right?
        # It's not like CyberSource will listen for a 400 response, and
        # we should be notified, which will happen automatically if save fails.
        #
        # response.full_clean()
        response.save()


class SubscriptionRequestResponse(Response):
    """
    All (non-confidential) specifics of CyberSource's response to a subscription request.
    """
    def __str__(self):
        return 'SubscriptionRequestResponse {}'.format(self.id)

    related_request = models.OneToOneField(
        SubscriptionRequest,
        related_name='subscription_request_response'
    )
    payment_token = models.CharField(
        max_length=26,
        blank=True,
        default=''
    )

    @property
    def subscription_agreement(self):
        return self.related_request.subscription_agreement

    @property
    def registrar(self):
        return self.related_request.subscription_agreement.registrar


class UpdateRequestResponse(Response):
    """
    All (non-confidential) specifics of CyberSource's response to an update request.
    """
    def __str__(self):
        return 'UpdateRequestResponse {}'.format(self.id)

    related_request = models.OneToOneField(
        UpdateRequest,
        related_name='update_request_response'
    )

    @property
    def subscription_agreement(self):
        return self.related_request.subscription_agreement

    @property
    def registrar(self):
        return self.related_request.subscription_agreement.registrar
