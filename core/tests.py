from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from .models import CustomUser, Transactions, Splitwise, FriendRequest
from datetime import date

class TransactionBusinessLogicTests(APITestCase):
    def setUp(self):
        # Create test users
        self.risk_taker = CustomUser.objects.create_user(
            username='risktaker',
            email='risktaker@test.com',
            password='testpass123'
        )
        
        self.syndicator1 = CustomUser.objects.create_user(
            username='syndicator1',
            email='syndicator1@test.com',
            password='testpass123'
        )
        
        self.syndicator2 = CustomUser.objects.create_user(
            username='syndicator2',
            email='syndicator2@test.com',
            password='testpass123'
        )
        
        # Create friend relationships
        FriendRequest.objects.create(
            user_id=self.risk_taker,
            requested_id=self.syndicator1,
            status='accepted'
        )
        
        FriendRequest.objects.create(
            user_id=self.risk_taker,
            requested_id=self.syndicator2,
            status='accepted'
        )
        
        # Authenticate as risk taker
        self.client.force_authenticate(user=self.risk_taker)
    
    def test_case_1_solo_transaction_auto_create_splitwise(self):
        """Test Case 1: Solo transaction - auto-create splitwise entry for risk taker"""
        data = {
            "total_principal_amount": 1000,
            "total_interest_amount": 200,  # 20% interest
            "risk_taker_flag": False,
            "risk_taker_commission": 0
        }
        
        response = self.client.post(reverse('create_transaction'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify transaction was created
        transaction = Transactions.objects.get(risk_taker_id=self.risk_taker)
        self.assertEqual(transaction.total_principal_amount, 1000)
        self.assertEqual(transaction.total_interest, 200)
        self.assertFalse(transaction.risk_taker_flag)
        
        # Verify single splitwise entry was auto-created for risk taker
        splitwise_entries = Splitwise.objects.filter(transaction_id=transaction)
        self.assertEqual(splitwise_entries.count(), 1)
        
        splitwise_entry = splitwise_entries.first()
        self.assertEqual(splitwise_entry.syndicator_id, self.risk_taker)
        self.assertEqual(splitwise_entry.principal_amount, 1000)
        self.assertEqual(splitwise_entry.interest_amount, 200)
        self.assertEqual(splitwise_entry.get_interest_after_commission(), 200)  # No commission
        self.assertEqual(splitwise_entry.get_commission_deducted(), 0)
    
    def test_case_2_syndicated_transaction_no_commission(self):
        """Test Case 2: Syndicated transaction with multiple syndicators, no commission"""
        data = {
            "total_principal_amount": 1000,
            "total_interest_amount": 200,  # 20% interest
            "risk_taker_flag": False,
            "risk_taker_commission": 0,
            "syndicate_details": {
                "syndicator1": {
                    "principal_amount": 600,
                    "interest": 200
                },
                "syndicator2": {
                    "principal_amount": 400,
                    "interest": 200
                }
            }
        }
        
        response = self.client.post(reverse('create_transaction'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify transaction and splitwise entries
        transaction = Transactions.objects.get(risk_taker_id=self.risk_taker)
        splitwise_entries = Splitwise.objects.filter(transaction_id=transaction)
        self.assertEqual(splitwise_entries.count(), 2)
        
        # Check each syndicator's entry
        for entry in splitwise_entries:
            self.assertEqual(entry.interest_amount, 200)  # Original interest
            self.assertEqual(entry.get_interest_after_commission(), 200)  # No commission
            self.assertEqual(entry.get_commission_deducted(), 0)
    
    def test_case_3_commission_only_risk_taker_not_in_splitwise(self):
        """Test Case 3: Commission transaction where risk taker is NOT in splitwise"""
        data = {
            "total_principal_amount": 1000,
            "total_interest_amount": 200,  # 20% interest
            "risk_taker_flag": True,
            "risk_taker_commission": 50,  # 50% commission
            "syndicate_details": {
                "syndicator1": {
                    "principal_amount": 600,
                    "interest": 200
                },
                "syndicator2": {
                    "principal_amount": 400,
                    "interest": 200
                }
            }
        }
        
        response = self.client.post(reverse('create_transaction'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify transaction
        transaction = Transactions.objects.get(risk_taker_id=self.risk_taker)
        self.assertTrue(transaction.risk_taker_flag)
        self.assertEqual(transaction.risk_taker_commission, 50)
        
        # Verify splitwise entries - each syndicator pays 50% of their actual interest amount
        splitwise_entries = Splitwise.objects.filter(transaction_id=transaction)
        self.assertEqual(splitwise_entries.count(), 2)
        
        total_commission_earned = 0
        for entry in splitwise_entries:
            self.assertEqual(entry.interest_amount, 200)  # Original interest percentage
            # Calculate actual interest amount: principal * interest_percentage / 100
            actual_interest = entry.principal_amount * entry.interest_amount / 100
            # Calculate commission: 50% of actual interest
            expected_commission = actual_interest * 0.5
            # Calculate interest after commission
            expected_interest_after_commission = actual_interest - expected_commission
            
            print(f"Entry: {entry.syndicator_id.username}")
            print(f"  Principal: {entry.principal_amount}")
            print(f"  Interest %: {entry.interest_amount}")
            print(f"  Actual interest: {actual_interest}")
            print(f"  Expected commission: {expected_commission}")
            print(f"  Expected interest after commission: {expected_interest_after_commission}")
            print(f"  Actual interest after commission: {entry.get_interest_after_commission()}")
            print(f"  Actual commission deducted: {entry.get_commission_deducted()}")
            
            self.assertEqual(entry.get_interest_after_commission(), expected_interest_after_commission)
            commission_deducted = entry.get_commission_deducted()
            self.assertEqual(commission_deducted, expected_commission)
            total_commission_earned += commission_deducted
        
        # Verify total commission earned is the sum of all commission deducted
        # Syndicator1: 600 * 2% = 12, commission = 6
        # Syndicator2: 400 * 2% = 8, commission = 4
        # Total commission = 6 + 4 = 10
        self.assertEqual(total_commission_earned, 10)
    
    def test_case_4_commission_with_risk_taker_in_splitwise(self):
        """Test Case 4: Commission transaction where risk taker IS in splitwise (shouldn't pay commission to themselves)"""
        data = {
            "total_principal_amount": 1000,
            "total_interest_amount": 200,  # 20% interest
            "risk_taker_flag": True,
            "risk_taker_commission": 50,  # 50% commission
            "syndicate_details": {
                "risktaker": {  # Risk taker is also a syndicator
                    "principal_amount": 400,
                    "interest": 200
                },
                "syndicator1": {
                    "principal_amount": 600,
                    "interest": 200
                }
            }
        }
        
        response = self.client.post(reverse('create_transaction'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Verify transaction
        transaction = Transactions.objects.get(risk_taker_id=self.risk_taker)
        self.assertTrue(transaction.risk_taker_flag)
        self.assertEqual(transaction.risk_taker_commission, 50)
        
        # Verify splitwise entries
        splitwise_entries = Splitwise.objects.filter(transaction_id=transaction)
        self.assertEqual(splitwise_entries.count(), 2)
        
        # Find risk taker's entry
        risk_taker_entry = splitwise_entries.get(syndicator_id=self.risk_taker)
        self.assertEqual(risk_taker_entry.interest_amount, 200)  # Original interest
        self.assertEqual(risk_taker_entry.get_interest_after_commission(), 200)  # No commission (to themselves)
        self.assertEqual(risk_taker_entry.get_commission_deducted(), 0)
        
        # Find other syndicator's entry
        other_entry = splitwise_entries.exclude(syndicator_id=self.risk_taker).first()
        self.assertEqual(other_entry.interest_amount, 200)  # Original interest percentage
        # Calculate actual interest: 600 * 2% = 12
        actual_interest = other_entry.principal_amount * other_entry.interest_amount / 100
        # Calculate commission: 50% of 12 = 6
        expected_commission = actual_interest * 0.5
        # Calculate interest after commission: 12 - 6 = 6
        expected_interest_after_commission = actual_interest - expected_commission
        
        self.assertEqual(other_entry.get_interest_after_commission(), expected_interest_after_commission)
        self.assertEqual(other_entry.get_commission_deducted(), expected_commission)
        
        # Verify total commission earned is only from the other syndicator (risk taker doesn't pay commission to themselves)
        total_commission_earned = risk_taker_entry.get_commission_deducted() + other_entry.get_commission_deducted()
        self.assertEqual(total_commission_earned, 6)  # 0 + 6 = 6
    
    def test_commission_validation_exceeds_available_interest(self):
        """Test that commission cannot exceed 100%"""
        data = {
            "total_principal_amount": 1000,
            "total_interest_amount": 200,
            "risk_taker_flag": True,
            "risk_taker_commission": 150,  # Exceeds 100%
            "syndicate_details": {
                "syndicator1": {
                    "principal_amount": 1000,
                    "interest": 200
                }
            }
        }
        
        response = self.client.post(reverse('create_transaction'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("risk_taker_commission must be between 0 and 100", response.data['error'])
    
    def test_commission_validation_with_risk_taker_in_splitwise(self):
        """Test commission validation when risk taker is in splitwise (should exclude them from commission calculation)"""
        data = {
            "total_principal_amount": 1000,
            "total_interest_amount": 200,
            "risk_taker_flag": True,
            "risk_taker_commission": 80,  # Should be valid since it's a percentage
            "syndicate_details": {
                "risktaker": {
                    "principal_amount": 500,
                    "interest": 200
                },
                "syndicator1": {
                    "principal_amount": 500,
                    "interest": 200
                }
            }
        }
        
        response = self.client.post(reverse('create_transaction'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)  # Should succeed since commission is a percentage

class SplitwiseModelTests(TestCase):
    def setUp(self):
        self.risk_taker = CustomUser.objects.create_user(
            username='risktaker',
            email='risktaker@test.com',
            password='testpass123'
        )
        
        self.syndicator = CustomUser.objects.create_user(
            username='syndicator',
            email='syndicator@test.com',
            password='testpass123'
        )
    
    def test_get_interest_after_commission_no_commission(self):
        """Test interest calculation when no commission is applied"""
        transaction = Transactions.objects.create(
            risk_taker_id=self.risk_taker,
            total_principal_amount=1000,
            total_interest=200,
            risk_taker_flag=False,
            risk_taker_commission=0,
            month_period_of_loan=1,
            start_date=date.today(),
            end_date=date.today(),
            lender_name='test lender'
        )
        
        splitwise_entry = Splitwise.objects.create(
            transaction_id=transaction,
            syndicator_id=self.syndicator,
            principal_amount=1000,
            interest_amount=200
        )
        
        self.assertEqual(splitwise_entry.get_interest_after_commission(), 200)
        self.assertEqual(splitwise_entry.get_commission_deducted(), 0)
    
    def test_get_interest_after_commission_with_commission(self):
        """Test interest calculation when commission is applied"""
        transaction = Transactions.objects.create(
            risk_taker_id=self.risk_taker,
            total_principal_amount=1000,
            total_interest=200,
            risk_taker_flag=True,
            risk_taker_commission=50,  # 50% commission
            month_period_of_loan=1,
            start_date=date.today(),
            end_date=date.today(),
            lender_name='test lender'
        )
        
        splitwise_entry = Splitwise.objects.create(
            transaction_id=transaction,
            syndicator_id=self.syndicator,
            principal_amount=1000,
            interest_amount=200  # 20% interest
        )
        
        # Calculate actual interest: 1000 * 20% = 200
        actual_interest = splitwise_entry.principal_amount * splitwise_entry.interest_amount / 100
        # Calculate commission: 50% of 200 = 100
        expected_commission = actual_interest * 0.5
        # Calculate interest after commission: 200 - 100 = 100
        expected_interest_after_commission = actual_interest - expected_commission
        
        self.assertEqual(splitwise_entry.get_interest_after_commission(), expected_interest_after_commission)
        self.assertEqual(splitwise_entry.get_commission_deducted(), expected_commission)
    
    def test_risk_taker_does_not_pay_commission_to_themselves(self):
        """Test that risk taker doesn't pay commission to themselves"""
        transaction = Transactions.objects.create(
            risk_taker_id=self.risk_taker,
            total_principal_amount=1000,
            total_interest=200,
            risk_taker_flag=True,
            risk_taker_commission=50,  # 50% commission
            month_period_of_loan=1,
            start_date=date.today(),
            end_date=date.today(),
            lender_name='test lender'
        )
        
        # Create entry for risk taker
        risk_taker_entry = Splitwise.objects.create(
            transaction_id=transaction,
            syndicator_id=self.risk_taker,
            principal_amount=500,
            interest_amount=200  # 20% interest
        )
        
        # Create entry for other syndicator
        syndicator_entry = Splitwise.objects.create(
            transaction_id=transaction,
            syndicator_id=self.syndicator,
            principal_amount=500,
            interest_amount=200  # 20% interest
        )
        
        # Risk taker should not pay commission to themselves
        # Risk taker's actual interest: 500 * 20% = 100
        risk_taker_actual_interest = risk_taker_entry.principal_amount * risk_taker_entry.interest_amount / 100
        self.assertEqual(risk_taker_entry.get_interest_after_commission(), risk_taker_actual_interest)
        self.assertEqual(risk_taker_entry.get_commission_deducted(), 0)
        
        # Other syndicator should pay 50% commission
        # Other syndicator's actual interest: 500 * 20% = 100
        other_actual_interest = syndicator_entry.principal_amount * syndicator_entry.interest_amount / 100
        # Commission: 50% of 100 = 50
        expected_commission = other_actual_interest * 0.5
        # Interest after commission: 100 - 50 = 50
        expected_interest_after_commission = other_actual_interest - expected_commission
        
        self.assertEqual(syndicator_entry.get_interest_after_commission(), expected_interest_after_commission)
        self.assertEqual(syndicator_entry.get_commission_deducted(), expected_commission)
