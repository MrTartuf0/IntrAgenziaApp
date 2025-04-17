import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:go_router/go_router.dart';
import 'package:intr_agenzia_app/io/dio_interceptor.dart';
import 'package:intr_agenzia_app/io/secure_storage_handler.dart';
import 'package:pretty_dio_logger/pretty_dio_logger.dart';
import 'package:top_snackbar_flutter/top_snack_bar.dart';
import 'package:top_snackbar_flutter/custom_snack_bar.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({Key? key}) : super(key: key);

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final TextEditingController _emailController = TextEditingController(
    text: 'vitaliydidyk16@gmail.com',
  );
  final TextEditingController _passwordController = TextEditingController(
    text: 'RxzmdNh7S4fw9!7',
  );

  final Dio _dio = Dio();

  @override
  void initState() {
    super.initState();
    _dio.interceptors.add(
      PrettyDioLogger(requestHeader: true, responseHeader: true),
    );
  }

  Future<void> _login() async {
    try {
      final response = await _dio.post(
        'https://intragenzia.adisu.umbria.it/user/login',
        options: Options(
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          followRedirects: false,
          validateStatus: (status) => true,
        ),
        data: {
          'name': _emailController.text,
          'pass': _passwordController.text,
          'form_id': 'user_login_form',
        },
      );

      if (response.headers['set-cookie'] == null) {
        print("BRO MANCANO I BISCOTTI, vai a comprare le gocciole");
        showTopSnackBar(
          Overlay.of(context),
          CustomSnackBar.error(message: "Credenziali errate."),
        );
      } else {
        final cookie = response.headers['set-cookie']![0].split(';')[0];
        SecureStorageService().saveCredentials(
          email: _emailController.text,
          password: _passwordController.text,
          cookie: cookie,
        );

        context.go('/home');
      }
    } catch (e) {}
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 30.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Text(
                'Login',
                style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 30),
              TextField(
                controller: _emailController,
                decoration: InputDecoration(
                  hintText: 'Email',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
              const SizedBox(height: 15),
              TextField(
                controller: _passwordController,
                obscureText: true,
                decoration: InputDecoration(
                  hintText: 'Password',
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(8),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                height: 45,
                child: ElevatedButton(
                  onPressed: _login,
                  child: const Text('Login'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }
}
