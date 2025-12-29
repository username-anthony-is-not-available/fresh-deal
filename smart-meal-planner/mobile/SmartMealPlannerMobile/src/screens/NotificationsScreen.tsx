// src/screens/NotificationsScreen.tsx
import React from 'react';
import {View, Text, StyleSheet} from 'react-native';

const NotificationsScreen = () => {
  return (
    <View style={styles.container}>
      <Text style={styles.text}>Notifications Screen</Text>
      <Text style={styles.subtext}>
        This feature is coming soon!
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f5f5f5',
  },
  text: {
    fontSize: 20,
    fontWeight: 'bold',
  },
  subtext: {
    fontSize: 16,
    color: '#666',
    marginTop: 8,
  },
});

export default NotificationsScreen;
