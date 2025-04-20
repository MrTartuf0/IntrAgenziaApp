import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:intr_agenzia_app/io/secure_storage_handler.dart';
import 'package:intr_agenzia_app/pages/home.dart';
import 'package:intr_agenzia_app/pages/login.dart';

final GoRouter appRouter = GoRouter(
  initialLocation: '/',
  redirect: (BuildContext context, GoRouterState state) async {
    final cookie = await SecureStorageService().getCookie();

    final isLoggedIn = cookie != null && cookie.isNotEmpty;
    final isAtLogin = state.uri.path == '/login' || state.uri.path == '/';

    if (!isLoggedIn && !isAtLogin) {
      return '/login';
    } else if (isLoggedIn && isAtLogin) {
      return '/home';
    }

    return null; // No redirect
  },
  routes: [
    GoRoute(path: '/', builder: (context, state) => const LoginScreen()),
    GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
    GoRoute(path: '/home', builder: (context, state) => const HomeScreen()),
  ],
);
