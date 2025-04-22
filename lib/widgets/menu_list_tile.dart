import 'package:flutter/material.dart';

class MenuListTile extends StatelessWidget {
  final String title;
  final String nodeID;
  final IconData icon;
  final Color iconColor;
  final bool enabled;

  const MenuListTile({
    super.key,
    required this.title,
    required this.nodeID,
    required this.icon,
    required this.iconColor,
    this.enabled = true,
  });

  @override
  Widget build(BuildContext context) {
    return ListTile(
      tileColor:
          iconColor == Colors.orangeAccent
              ? const Color.fromARGB(255, 255, 247, 234)
              : const Color.fromARGB(255, 249, 245, 255),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      enabled: enabled,
      leading: Icon(icon, color: iconColor),
      title: Text(
        title.isEmpty ? 'Menu non disponibile' : title,
        style: const TextStyle(fontWeight: FontWeight.bold),
      ),
      trailing: const Icon(Icons.chevron_right),
      onTap:
          enabled
              ? () {
                print('Tapped nodeID: $nodeID');
              }
              : null,
    );
  }
}
