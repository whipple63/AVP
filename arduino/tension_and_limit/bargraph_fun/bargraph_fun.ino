/*************************************************** 
 ****************************************************/

#include <Wire.h>
#include "Adafruit_LEDBackpack.h"
#include "Adafruit_GFX.h"

Adafruit_24bargraph bar = Adafruit_24bargraph();

void setup() {
  Serial.begin(9600);
  Serial.println("HT16K33 Bi-Color Bargraph test");
  
  bar.begin(0x70);  // pass in the address

  play_with_lights();
}


void loop() {
  delay(2000);
  play_with_lights();
}

void play_with_lights() {
  
  for (uint8_t b=0; b<24; b++ ){
    bar.setBar(b, LED_RED);
  }
  for (uint8_t i=0; i<=15; i++) {
    bar.setBrightness(i);
    bar.writeDisplay();
    delay(20);
  }
  for (uint8_t j=0; j<=10; j++){
    for (uint8_t b=0; b<24; b++ ){
      bar.setBar(b, LED_YELLOW);
    }
    bar.writeDisplay();
    delay(j);
    for (uint8_t b=0; b<24; b++ ){
      bar.setBar(b, LED_RED);
    }
    bar.writeDisplay();
    delay(10-j);
  }

  for (uint8_t j=0; j<=10; j++){
    for (uint8_t b=0; b<24; b++ ){
      bar.setBar(b, LED_GREEN);
    }
    bar.writeDisplay();
    delay(j);
    for (uint8_t b=0; b<24; b++ ){
      bar.setBar(b, LED_YELLOW);
    }
    bar.writeDisplay();
    delay(10-j);
  }

  int bar_array[24];
  for (uint8_t b=0; b<24; b++ ){
    bar.setBar(b, LED_GREEN);
    bar_array[b] = 1;
  }
  bar.writeDisplay();
  
  for (uint8_t b=0; b<24; b++ ){
    int r = random(0,24);
    while (bar_array[r] != 1) { r = random(0,24); }
    bar_array[r] = 0;
    bar.setBar(r, LED_OFF);
    delay(10);
    bar.writeDisplay();
  }

}
