from django.urls import path

from governance import api, identity

from .web import index, readiness

urlpatterns = [
    path('', index),
    path('health/ready', readiness),
    path('health/live', api.liveness),
    path('api/v1/config', identity.bootstrap),
    path('api/v1/auth/demo', identity.demo_login),
    path('api/v1/auth/logout', identity.sign_out),
    path('auth/login', identity.oidc_login),
    path('auth/callback', identity.oidc_callback),
    path('api/v1/me', api.MeView.as_view()),
    path('api/v1/assemblies', api.AssemblyListView.as_view()),
    path('api/v1/assemblies/<uuid:assembly_id>/state', api.StateView.as_view()),
    path('api/v1/assemblies/<uuid:assembly_id>/presence/<str:action>', api.PresenceView.as_view()),
    path('api/v1/assemblies/<uuid:assembly_id>/proxies', api.ProxyView.as_view()),
    path('api/v1/assemblies/<uuid:assembly_id>/proxies/claim', api.ProxyClaimView.as_view()),
    path(
        'api/v1/assemblies/<uuid:assembly_id>/proxies/<uuid:proxy_id>/revoke', api.ProxyRevokeView.as_view()
    ),
    path('api/v1/assemblies/<uuid:assembly_id>/install', api.InstallView.as_view()),
    path('api/v1/assemblies/<uuid:assembly_id>/agenda/<uuid:item_id>/open', api.OpenView.as_view()),
    path('api/v1/assemblies/<uuid:assembly_id>/rounds/<uuid:round_id>/ballots', api.BallotView.as_view()),
    path('api/v1/assemblies/<uuid:assembly_id>/rounds/<uuid:round_id>/close', api.CloseRoundView.as_view()),
    path('api/v1/assemblies/<uuid:assembly_id>/floor', api.FloorView.as_view()),
    path(
        'api/v1/assemblies/<uuid:assembly_id>/floor/<uuid:floor_id>/decision', api.FloorDecisionView.as_view()
    ),
    path('api/v1/assemblies/<uuid:assembly_id>/close', api.CloseAssemblyView.as_view()),
    path('api/v1/assemblies/<uuid:assembly_id>/new-demo', api.NewDemoView.as_view()),
    path('api/v1/assemblies/<uuid:assembly_id>/minutes', api.MinutesView.as_view()),
    path('api/v1/demo/inbox', api.InboxView.as_view()),
    path('api/v1/assemblies/<uuid:assembly_id>/minutes.html', api.MinutesHtmlView.as_view()),
    path('api/v1/admin/organization', api.AdminOrganizationView.as_view()),
    path('api/v1/admin/members/import', api.AdminImportView.as_view()),
    path('api/v1/admin/assemblies', api.AdminAssembliesView.as_view()),
    path('api/v1/admin/assemblies/<uuid:assembly_id>', api.AdminAssemblyView.as_view()),
    path('api/v1/admin/assemblies/<uuid:assembly_id>/agenda', api.AdminAgendaView.as_view()),
    path(
        'api/v1/admin/assemblies/<uuid:assembly_id>/agenda/<uuid:item_id>/remove',
        api.AdminAgendaRemoveView.as_view(),
    ),
    path('api/v1/admin/assemblies/<uuid:assembly_id>/publish', api.AdminPublishView.as_view()),
]
