import 'package:flutter/material.dart';
import 'package:gap/gap.dart';
import 'package:intr_agenzia_app/scraper/name_node.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  Future<List<Map<String, String>>>? todayMenus;
  Future<List<Map<String, String>>>? tomorrowMenus;

  @override
  void initState() {
    saveMenus();
    super.initState();
  }

  void saveMenus() async {
    final response = await fetchPascoliMenus();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: EdgeInsets.only(top: 24, left: 32, right: 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Buongiorno 🌤️ vit',
                style: TextStyle(fontSize: 36, fontWeight: FontWeight.bold),
              ),
              Gap(16),
              Divider(),
              Text(
                'Buongiorno 🌤️ vit',
                style: TextStyle(fontSize: 36, fontWeight: FontWeight.bold),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
