import 'package:go_router/go_router.dart';
import 'package:intr_agenzia_app/pages/home.dart';
import 'package:intr_agenzia_app/pages/login.dart';

final GoRouter appRouter = GoRouter(
  routes: [
    GoRoute(path: '/', builder: (context, state) => const LoginScreen()),
    GoRoute(path: '/login', builder: (context, state) => const LoginScreen()),
    GoRoute(path: '/home', builder: (context, state) => const HomeScreen()),
  ],
);
