import 'package:flutter/material.dart';
import 'package:gap/gap.dart';
import 'package:go_router/go_router.dart';
import 'package:intr_agenzia_app/io/secure_storage_handler.dart';
import 'package:intr_agenzia_app/scraper/menu_node.dart';
import 'package:intr_agenzia_app/scraper/username.dart';
import 'package:intr_agenzia_app/widgets/menu_list_tile.dart'; // update path accordingly

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  String todayLaunchPName = '';
  String todayLaunchPNode = '';
  String todayDinnerPName = '';
  String todayDinnerPNode = '';

  String tomorrowLaunchPName = '';
  String tomorrowLaunchPNode = '';
  String tomorrowDinnerPName = '';
  String tomorrowDinnerPNode = '';

  String userName = '';

  @override
  void initState() {
    saveMenus();
    saveUsername();
    super.initState();
  }

  void saveMenus() async {
    final res = await fetchPascoliMenus();
    setState(() {
      todayLaunchPName = res['mensaList']![0];
      todayLaunchPNode = res['nodeList']![0];
      todayDinnerPName = res['mensaList']![1];
      todayDinnerPNode = res['nodeList']![1];

      tomorrowLaunchPName = res['mensaList']![2];
      tomorrowLaunchPNode = res['nodeList']![2];
      tomorrowDinnerPName = res['mensaList']![3];
      tomorrowDinnerPNode = res['nodeList']![3];
    });
  }

  void saveUsername() async {
    final res = await fetchUserFullName();
    setState(() {
      userName = res;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.only(top: 24, left: 32, right: 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Buongiorno 🌤️',
                style: TextStyle(fontSize: 36, fontWeight: FontWeight.bold),
              ),
              Text(
                userName,
                style: const TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const Gap(8),
              const Divider(),
              const Gap(16),
              const Text(
                'Oggi',
                style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold),
              ),
              const Gap(16),

              MenuListTile(
                title: todayLaunchPName,
                icon: Icons.wb_sunny,
                iconColor: Colors.orangeAccent,
                enabled: todayLaunchPName.isNotEmpty,
              ),

              const Gap(12),

              MenuListTile(
                title: todayDinnerPName,
                icon: Icons.nightlight_round,
                iconColor: Colors.purple,
                enabled: todayDinnerPName.isNotEmpty,
              ),

              const Gap(24),
              const Divider(),

              const Text(
                'Domani',
                style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold),
              ),

              const Gap(16),

              MenuListTile(
                title: tomorrowLaunchPName,
                icon: Icons.wb_sunny,
                iconColor: Colors.orangeAccent,
                enabled: tomorrowLaunchPName.isNotEmpty,
              ),

              const Gap(12),

              MenuListTile(
                title: tomorrowDinnerPName,
                icon: Icons.nightlight_round,
                iconColor: Colors.purple,
                enabled: tomorrowDinnerPName.isNotEmpty,
              ),

              const Gap(24),
              const Divider(),
              const Gap(32),

              Center(
                child: ElevatedButton(
                  onPressed: () async {
                    await SecureStorageService().delete('user_cookie');
                    context.go('/login');
                  },
                  child: const Text('Logout'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
