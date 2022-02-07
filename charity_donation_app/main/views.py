import datetime
from django.core.paginator import Paginator, EmptyPage
from django.shortcuts import render, redirect
from django.views import View
from main.models import Institution, Donation, InstitutionCategories, Category, DonationCategories, \
    TokenTemporaryStorage
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import check_password
from datetime import date
from django.contrib import messages
from django.core.mail import send_mail
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str, DjangoUnicodeDecodeError
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.sites.shortcuts import get_current_site
from .utils import token_generator
from django.core.exceptions import ObjectDoesNotExist


class LandingPageView(View):
    def get(self, request):
        supported_institutions = len(Institution.objects.all())
        bag_quantity = 0
        for donation in Donation.objects.all():
            bag_quantity += donation.quantity
        foundation_list = Institution.objects.filter(type=1)
        organization_list = Institution.objects.filter(type=2)
        local_collection_list = Institution.objects.filter(type=3)
        foundation_paginator = Paginator(foundation_list, 5)
        organization_paginator = Paginator(organization_list, 5)
        local_collection_paginator = Paginator(local_collection_list, 5)
        page_num = request.GET.get('page', 1)
        try:
            foundations = foundation_paginator.page(page_num)
        except EmptyPage:
            foundations = foundation_paginator.page(1)
        try:
            organizations = organization_paginator.page(page_num)
        except EmptyPage:
            organizations = organization_paginator.page(1)
        try:
            local_collections = local_collection_paginator.page(page_num)
        except EmptyPage:
            local_collections = local_collection_paginator.page(1)
        institution_categories = InstitutionCategories.objects.all()
        return render(request, 'index.html', {'supported_institutions': supported_institutions,
                                              'bag_quantity': bag_quantity,
                                              'foundations': foundations,
                                              'organizations': organizations,
                                              'local_collections': local_collections,
                                              'institution_categories': institution_categories})

    def post(self, request):
        name = request.POST.get('name')
        surname = request.POST.get('surname')
        message = request.POST.get('message')
        email_subject = f'Contact form (Sent by user {name} {surname}'
        email_body = message
        administrators = User.objects.filter(is_superuser=True)

        if not name or not surname or not message:
            messages.error(request, 'Please fill all fields correctly')
            return redirect('/')

        for administrator in administrators:
            email = administrator.email
            send_mail(
                email_subject,
                email_body,
                'noreply@noreply.com',
                [email],
                fail_silently=False,
            )
        messages.success(request, 'Successfully sent')
        return redirect('/')


class AddDonationView(View):
    def get(self, request):
        categories = Category.objects.all()
        institutions = Institution.objects.all()
        institution_categories = InstitutionCategories.objects.all()
        return render(request, 'form.html', {'categories': categories,
                                             'institutions': institutions,
                                             'institution_categories': institution_categories})

    def post(self, request):
        quantity = request.POST.get('bags')
        institution = Institution.objects.get(name=request.POST.get('organization'))
        address = request.POST.get('address')
        city = request.POST.get('city')
        zip_code = request.POST.get('postcode')
        phone_number = request.POST.get('phone')
        pick_up_date = request.POST.get('date')
        pick_up_time = request.POST.get('time')
        pick_up_comment = request.POST.get('more_info')
        user = request.user
        try:
            donation = Donation.objects.create(
            quantity=quantity,
            institution=institution,
            address=address,
            city=city,
            zip_code=zip_code,
            phone_number=phone_number,
            pick_up_date=pick_up_date,
            pick_up_time=pick_up_time,
            pick_up_comment=pick_up_comment,
            user=user
        )

            checked_categories = request.POST.get('checked_categories_backend').split(',')
            for category_id in checked_categories:
                DonationCategories.objects.create(
                donation=donation,
                category=Category.objects.get(id=category_id)
                )

            email = request.user.email
            email_subject = f'Donation nr {donation.id}'
            email_body = f'Thank you for donating. Pick up date: {pick_up_date} at {pick_up_time}'
            send_mail(
            email_subject,
            email_body,
            'noreply@noreply.com',
            [email],
            fail_silently=False,
            )

            return render(request, 'form-confirmation.html')
        except ValueError:
            messages.error(request, 'Something went wrong')
            return redirect('/add_donation/')


class DonationDetailsView(View):
    def get(self, request, donation_id):
        donation = Donation.objects.get(id=donation_id)
        donation_categories = DonationCategories.objects.all()
        return render(request, 'donation-details.html', {'donation': donation,
                                                         'donation_categories': donation_categories})

    def post(self, request, donation_id):
        donation = Donation.objects.get(id=donation_id)
        donation_categories = DonationCategories.objects.all()
        is_taken = request.POST.get('is_taken')
        if is_taken == "true":
            donation.is_taken = True
            donation.date_taken = date.today()
            now = datetime.datetime.now()
            current_time = now.strftime("%H:%M:%S")
            donation.time_taken = current_time
            donation.save()
        else:
            donation.is_taken = False
            donation.save()
        return render(request, 'donation-details.html', {'donation': donation,
                                                         'donation_categories': donation_categories})


class LoginView(View):
    def get(self, request):
        return render(request, 'login.html')

    def post(self, request):
        try:
            email = request.POST.get('email')
            password = request.POST.get('password')
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                return redirect('/')
            elif not User.objects.get(email=email).check_password(password):
                messages.error(request, 'Incorrect password')
                return render(request, 'login.html')
        except ObjectDoesNotExist:
            messages.error(request, 'Given e-mail does not exist in the database')
            return render(request, 'login.html')


class RegisterView(View):
    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        name = request.POST.get('name')
        surname = request.POST.get('surname')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        if len(password) < 8 or len(password2) < 8:
            messages.error(request, 'Password too short (Min. 8 characters)')
            return render(request, 'register.html')
        elif any(not c.isalnum() for c in password2) is False \
                or any(c.isupper() for c in password2) is False \
                or any(c.islower() for c in password2) is False \
                or any(c.isdigit() for c in password2) is False :
            messages.error(request, 'The password does not have all special characters'
                                    '(There should be letters, lowercase letters, numbers and special characters)')
            return render(request, 'register.html')
        elif User.objects.filter(username=email):
            messages.error(request, 'A user with the given e-mail already exists')
            return render(request, 'register.html')
        elif password != password2:
            messages.error(request, 'Passwords mismatch')
            return render(request, 'register.html')
        user = User.objects.create_user(username=email, first_name=name, last_name=surname, email=email)
        user.set_password(password2)
        user.is_active = False
        user.save()

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)
        TokenTemporaryStorage.objects.create(user_id=user.id, token=token)
        domain = get_current_site(request).domain
        link = reverse('activate-page', kwargs={'uidb64': uidb64, 'token': token})
        email_subject = 'Activate your account'
        activation_url = f'http://{domain}{link}'
        email_body = f'Hello {user}, your activation link:  {activation_url}'
        send_mail(
            email_subject,
            email_body,
            'noreply@noreply.com',
            [email],
            fail_silently=False,
        )
        messages.success(request, 'Check your e-mail account for further information')
        return render(request, 'register.html')


class VerificationView(View):
    def get(self, request, uidb64, token):
        try:
            id = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(id=id)
            stored_token = TokenTemporaryStorage.objects.get(user=user).token
            if token == stored_token:
                TokenTemporaryStorage.objects.get(user=user).delete()
                if not token_generator.check_token(user, token):
                    messages.error(request, 'Account is already activated')
                    return redirect('login-page')
                if user.is_active:
                    return redirect('login-page')

                user.is_active = True
                user.save()

                messages.success(request, 'Account successfully activated')
                return redirect('login-page')
            else:
                messages.error(request, 'Incorrect link or account is already activated')
                return redirect('login-page')
        except ObjectDoesNotExist:
            messages.error(request, 'Incorrect link or account is already activated')
            return redirect('login-page')


class LogoutView(View):
    def get(self, request):
        logout(request)
        return redirect('/')


class UserPanelView(View):
    def get(self, request, user_id):
        donations = Donation.objects.filter(user_id=user_id).order_by('date_added') \
            .order_by('date_taken').order_by('time_taken').order_by('is_taken')
        donation_categories = DonationCategories.objects.all()
        return render(request, 'user_panel.html', {'donations': donations,
                                                   'donation_categories': donation_categories})
    
    def post(self, request, user_id):
        name = request.POST.get('name')
        surname = request.POST.get('surname')
        message = request.POST.get('message')
        email_subject = f'Contact form(Sent by user {name} {surname}'
        email_body = message
        administrators = User.objects.filter(is_superuser=True)

        if not name or not surname or not message:
            messages.error(request, 'Please fill all fields correctly')
            return redirect('/')

        for administrator in administrators:
            email = administrator.email
            send_mail(
                email_subject,
                email_body,
                'noreply@noreply.com',
                [email],
                fail_silently=False,
            )
        messages.success(request, 'Successfully sent')
        return redirect(f'/panel/{request.user.id}/')



class UserEditView(View):
    def get(self, request, user_id):
        if request.user.id != user_id:
            return redirect(f'/edit/{request.user.id}/')
        return render(request, 'user-edit.html')

    def post(self, request, user_id):
        user = User.objects.get(id=user_id)

        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        if not request.POST.get('password') or not request.POST.get('password2'):
            messages.error(request, 'Please fill all fields correctly')
            return render(request, 'user-edit.html')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        if password != password2:
            messages.error(request, 'Passwords mismatch')
            return render(request, 'user-edit.html')
        user = authenticate(request, username=request.user.email, password=password2)
        if user is None:
            messages.error(request, 'Incorrect password')
            return render(request, 'user-edit.html')
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.save()
        messages.success(request, 'Data has been changed')
        return redirect(f'/edit/{request.user.id}/')


class PasswordChangeView(View):
    def get(self, request, user_id):
        if request.user.id != user_id:
            return redirect(f'/edit/{request.user.id}/')
        return render(request, 'change-password.html')

    def post(self, request, user_id):
        if not request.POST.get('old_password') or not request.POST.get('new_password1') or not request.POST.get('new_password2'):
            messages.error(request, 'Please fill all fields correctly')
            return render(request, 'change-password.html')

        old_password = request.POST.get('old_password')
        user = authenticate(request, username=request.user.email, password=old_password)
        if user is None:
            messages.error(request, 'Old password incorrect')
            return render(request, 'change-password.html')

        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')
        if new_password1 != new_password2:
            messages.error(request, 'Passwords mismatch')
            return render(request, 'change-password.html')

        user.set_password(new_password1)
        user.save()
        new_user = authenticate(request, username=request.user.email, password=new_password1)
        if user is None:
            messages.error(request, 'Something went wrong')
            return render(request, 'change-password.html')
        login(request, new_user)
        messages.success(request, 'Data successfully changed')
        return redirect(f'/edit/{request.user.id}/')


class PasswordResetView(View):
    def get(self, request):
        return render(request, 'password-reset.html')

    def post(self, request):
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)
            TokenTemporaryStorage.objects.create(user_id=user.id, token=token)
            domain = get_current_site(request).domain
            link = reverse('password-reset-verification', kwargs={'uidb64': uidb64, 'token': token})
            email_subject = 'Password reset'
            activation_url = f'http://{domain}{link}'
            email_body = f'Hello {user}, twój password reset link:  {activation_url}'
            send_mail(
                email_subject,
                email_body,
                'noreply@noreply.com',
                [email],
                fail_silently=False,
            )
            messages.success(request, 'Check your e-mail inbox')
            return render(request, 'password-reset.html')
        except ObjectDoesNotExist:
            messages.error(request, 'Incorrect e-mail')
            return render(request, 'password-reset.html')


class PasswordResetVerificationView(View):
    def get(self, request, uidb64, token):
        try:
            id = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(id=id)
            stored_token = TokenTemporaryStorage.objects.get(user=user).token
            if token == stored_token:
                if not token_generator.check_token(user, token):
                    messages.error(request, 'Password has already been changed')
                    return redirect('login-page')
                return render(request, 'new-password-form.html')
            else:
                messages.error(request, 'Incorrect link or password is already changed')
                return redirect('login-page')
        except ObjectDoesNotExist:
            messages.error(request, 'Incorrect link or password is already changed')
            return redirect('login-page')

    def post(self, request, uidb64, token):
        id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(id=id)
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, 'Passwords mismatch')
            return render(request, 'new-password-form.html')

        user.set_password(password1)
        user.save()
        TokenTemporaryStorage.objects.get(user=user).delete()

        messages.success(request, 'Password changed successfully')
        return redirect('login-page')
