from __future__ import absolute_import

from json import dumps, loads

from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.views import login, password_change
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render_to_response
from django.template import RequestContext
from django.utils.http import urlencode
from django.utils.translation import ugettext_lazy as _
from django.views.generic.edit import CreateView, DeleteView, UpdateView
from django.views.generic.list import ListView

from permissions.models import Permission

from .conf.settings import LOGIN_METHOD
from .forms import (ChoiceForm, UserForm, UserForm_view, LicenseForm,
    EmailAuthenticationForm)


def multi_object_action_view(request):
    """
    Proxy view called first when using a multi object action, which
    then redirects to the appropiate specialized view
    """

    next = request.POST.get('next', request.GET.get('next', request.META.get('HTTP_REFERER', '/')))

    action = request.GET.get('action', None)
    id_list = u','.join([key[3:] for key in request.GET.keys() if key.startswith('pk_')])
    items_property_list = [loads(key[11:]) for key in request.GET.keys() if key.startswith('properties_')]

    if not action:
        messages.error(request, _(u'No action selected.'))
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

    if not id_list and not items_property_list:
        messages.error(request, _(u'Must select at least one item.'))
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

    # Separate redirects to keep backwards compatibility with older
    # functions that don't expect a properties_list parameter
    if items_property_list:
        return HttpResponseRedirect('%s?%s' % (
            action,
            urlencode({'items_property_list': dumps(items_property_list), 'next': next}))
        )
    else:
        return HttpResponseRedirect('%s?%s' % (
            action,
            urlencode({'id_list': id_list, 'next': next}))
        )


def get_obj_from_content_type_string(string):
    model, pk = string.split(u',')
    ct = ContentType.objects.get(model=model)
    return ct.get_object_for_this_type(pk=pk)


def assign_remove(request, left_list, right_list, add_method, remove_method, left_list_title, right_list_title, decode_content_type=False, extra_context=None, grouped=False):
    left_list_name = u'left_list'
    right_list_name = u'right_list'

    if request.method == 'POST':
        if u'%s-submit' % left_list_name in request.POST.keys():
            unselected_list = ChoiceForm(request.POST,
                prefix=left_list_name,
                choices=left_list())
            if unselected_list.is_valid():
                for selection in unselected_list.cleaned_data['selection']:
                    if grouped:
                        flat_list = []
                        for group in left_list():
                            flat_list.extend(group[1])
                    else:
                        flat_list = left_list()

                    label = dict(flat_list)[selection]
                    if decode_content_type:
                        selection_obj = get_obj_from_content_type_string(selection)
                    else:
                        selection_obj = selection
                    try:
                        add_method(selection_obj)
                        messages.success(request, _(u'%(selection)s added successfully added to %(right_list_title)s.') % {
                            'selection': label, 'right_list_title': right_list_title})
                    except:
                        if settings.DEBUG:
                            raise
                        else:
                            messages.error(request, _(u'Unable to add %(selection)s to %(right_list_title)s.') % {
                                'selection': label, 'right_list_title': right_list_title})

        elif u'%s-submit' % right_list_name in request.POST.keys():
            selected_list = ChoiceForm(request.POST,
                prefix=right_list_name,
                choices=right_list())
            if selected_list.is_valid():
                for selection in selected_list.cleaned_data['selection']:
                    if grouped:
                        flat_list = []
                        for group in right_list():
                            flat_list.extend(group[1])
                    else:
                        flat_list = right_list()

                    label = dict(flat_list)[selection]
                    if decode_content_type:
                        selection = get_obj_from_content_type_string(selection)
                    try:
                        remove_method(selection)
                        messages.success(request, _(u'%(selection)s added successfully removed from %(right_list_title)s.') % {
                            'selection': label, 'right_list_title': right_list_title})
                    except:
                        if settings.DEBUG:
                            raise
                        else:
                            messages.error(request, _(u'Unable to add %(selection)s to %(right_list_title)s.') % {
                                'selection': label, 'right_list_title': right_list_title})
    unselected_list = ChoiceForm(prefix=left_list_name,
        choices=left_list())
    selected_list = ChoiceForm(prefix=right_list_name,
        choices=right_list())

    context = {
        'subtemplates_list': [
            {
                'name': 'main/generic_form_subtemplate.html',
                'grid': 6,
                'context': {
                    'form': unselected_list,
                    'title': left_list_title,
                    'submit_label': _(u'Add'),
                    'submit_icon_famfam': 'add'
                }
            },
            {
                'name': 'main/generic_form_subtemplate.html',
                'grid': 6,
                'grid_clear': True,
                'context': {
                    'form': selected_list,
                    'title': right_list_title,
                    'submit_label': _(u'Remove'),
                    'submit_icon_famfam': 'delete'
                }
            },

        ],
    }
    if extra_context:
        context.update(extra_context)

    return render_to_response('main/generic_form.html', context,
        context_instance=RequestContext(request))


def current_user_details(request):
    """
    Display the current user's details
    """
    form = UserForm_view(instance=request.user)

    return render_to_response(
        'main/generic_form.html', {
            'form': form,
            'title': _(u'current user details'),
            'read_only': True,
        },
        context_instance=RequestContext(request))


def current_user_edit(request):
    """
    Allow an user to edit his own details
    """

    next = request.POST.get('next', request.GET.get('next', request.META.get('HTTP_REFERER', reverse('common:current_user_details'))))

    if request.method == 'POST':
        form = UserForm(instance=request.user, data=request.POST)
        if form.is_valid():
            if User.objects.filter(email=form.cleaned_data['email']).exclude(pk=request.user.pk).count():
                messages.error(request, _(u'E-mail conflict, another user has that same email.'))
            else:
                form.save()
                messages.success(request, _(u'Current user\'s details updated.'))
                return HttpResponseRedirect(next)
    else:
        form = UserForm(instance=request.user)

    return render_to_response(
        'main/generic_form.html', {
            'form': form,
            'next': next,
            'title': _(u'edit current user details'),
        },
        context_instance=RequestContext(request))


def login_view(request):
    """
    Control how the use is to be authenticated, options are 'email' and
    'username'
    """
    kwargs = {'template_name': 'main/login.html'}

    if LOGIN_METHOD == 'email':
        kwargs['authentication_form'] = EmailAuthenticationForm

    if not request.user.is_authenticated():
        context = {'web_theme_view_type': 'plain'}
    else:
        context = {}

    return login(request, extra_context=context, **kwargs)


def license_view(request):
    """
    Display the included LICENSE file from the about menu
    """
    form = LicenseForm()
    return render_to_response(
        'main/generic_detail.html', {
            'form': form,
            'title': _(u'License'),
        },
        context_instance=RequestContext(request))


def password_change_view(request):
    """
    Password change wrapper for better control
    """
    context = {'title': _(u'Current user password change')}

    return password_change(
        request,
        extra_context=context,
        template_name='main/password_change_form.html',
        post_change_redirect=reverse('common:password_change_done'),
    )


def password_change_done(request):
    """
    View called when the new user password has been accepted
    """

    messages.success(request, _(u'Your password has been successfully changed.'))
    return redirect('current_user_details')


class MayanPermissionCheckMixin(object):
    permissions_required = None

    def dispatch(self, request, *args, **kwargs):
        if self.permissions_required:
            Permission.objects.check_permissions(self.request.user, self.permissions_required)

        return super(MayanPermissionCheckMixin, self).dispatch(request, *args, **kwargs)


class MayanViewMixin(object):
    # TODO: split into two mixins, MayanView and ExtraContextMixin
    extra_context = {}
    post_action_redirect = None

    def dispatch(self, request, *args, **kwargs):
        self.next_url = self.request.POST.get('next', self.request.GET.get('next', self.post_action_redirect if self.post_action_redirect else self.request.META.get('HTTP_REFERER', '/')))
        self.previous_url = self.request.POST.get('previous', self.request.GET.get('previous', self.request.META.get('HTTP_REFERER', '/')))

        return super(MayanViewMixin, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(MayanViewMixin, self).get_context_data(**kwargs)
        context.update(
            {
                'next': self.next_url,
                'previous': self.previous_url
            }
        )

        context.update(self.extra_context)

        return context


class SingleObjectEditView(MayanPermissionCheckMixin, MayanViewMixin, UpdateView):
    template_name = 'main/generic_form.html'

    def form_invalid(self, form):
        result = super(SingleObjectEditView, self).form_invalid(form)

        try:
            messages.error(self.request, _('Error saving %s details.') % self.extra_context['object_name'])
        except KeyError:
            messages.error(self.request, _('Error saving details.'))

        return result

    def form_valid(self, form):
        result = super(SingleObjectEditView, self).form_valid(form)

        try:
            messages.success(self.request, _('%s details saved successfully.') % self.extra_context['object_name'].capitalize())
        except KeyError:
            messages.success(self.request, _('Details saved successfully.'))

        return result


class SingleObjectCreateView(MayanPermissionCheckMixin, MayanViewMixin, CreateView):
    template_name = 'main/generic_form.html'

    def form_invalid(self, form):
        result = super(SingleObjectCreateView, self).form_invalid(form)

        try:
            messages.error(self.request, _('Error creating new %s.') % self.extra_context['object_name'])
        except KeyError:
            messages.error(self.request, _('Error creating object.'))

        return result

    def form_valid(self, form):
        result = super(SingleObjectCreateView, self).form_valid(form)
        try:
            messages.success(self.request, _('%s created successfully.') % self.extra_context['object_name'].capitalize())
        except KeyError:
            messages.success(self.request, _('New object created successfully.'))

        return result


class SingleObjectDeleteView(MayanPermissionCheckMixin, MayanViewMixin, DeleteView):
    template_name = 'main/generic_confirm.html'

    def get_context_data(self, **kwargs):
        context = super(SingleObjectDeleteView, self).get_context_data(**kwargs)
        context.update({'delete_view': True})
        return context

    def delete(self, request, *args, **kwargs):
        try:
            result = super(SingleObjectDeleteView, self).delete(request, *args, **kwargs)
        except Exception as exception:
            try:
                messages.error(self.request, _('Error deleting %s.') % self.extra_context['object_name'])
            except KeyError:
                messages.error(self.request, _('Error deleting object.'))

            raise exception
        else:
            try:
                messages.success(self.request, _('%s deleted successfully.') % self.extra_context['object_name'].capitalize())
            except KeyError:
                messages.success(self.request, _('Object deleted successfully.'))

            return result


class SingleObjectListView(MayanPermissionCheckMixin, MayanViewMixin, ListView):
    # TODO: filter object_list by permission
    template_name = 'main/generic_list.html'
