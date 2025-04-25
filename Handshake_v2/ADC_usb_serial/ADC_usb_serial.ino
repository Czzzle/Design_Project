#include <SPI.h>
#include <IntervalTimer.h>

#include "usb_dev.h"
#include "usb_serial.h"


//------------ DAC PART ------------
// Pin definitions
const int DAC_MISO = 12; // 
const int DAC_MOSI = 11;
const int DAC_SCLK = 13; // 
const int DAC_CS = 10 ;// 


//------------ ADC PART ------------
const int ADC_MISO = 39; // Dout
const int ADC_MOSI = 26;
const int ADC_SCLK = 27; // CLK
const int ADC_CS = 38 ;// CONVST (CS

//------------- time related setting -------
const int SCLK = 20000000;  // SCLK = 20 MHz
volatile float samplingRate = 392000.0; // 392 kHz
volatile float periodMicros = 1.0;

IntervalTimer timer; // Teensy-specific high-precision timer

// ================= USB handshake definition ===========
// flags for states
volatile bool sendSample = false; // initally, no samples will be sent to PC.
volatile bool timerStart = false; //initially, no timer is working

volatile int MAX_BUFFER_SIZE = 1024;
volatile int HALF_MAX_BUFFER_SIZE = 512;
#define SUPER_MAX_BUFFER_SIZE  81920 //for 180K SR//40960 for 108K SR
#define SUPER_HALF_MAX_BUFFER_SIZE SUPER_MAX_BUFFER_SIZE/2
#define PACKET_SIZE 512


uint8_t byte_buffer[SUPER_MAX_BUFFER_SIZE]; //byte buffer 
volatile int nextPut = 0; //the index of the next ADC value
volatile int nextSend = 0; // the index of the next bunch of data MCU will send to PC
volatile int buffer_size = 0;

volatile int totalPut = 0;
volatile int totalSend = 0;

int coming_size; // coming size from PC, initilze here

// =============== Test LED def ===========
#define LED 2
#define LED2 3

#define LED_RED 33
#define LED_YELLOW 34

// =============== UART DEF ============
// set this to the hardware serial port you wish to use
#define HWSERIAL Serial7

void setup() {
  // put your setup code here, to run once:
  HWSERIAL.begin(115200); //begin HW serial

  SPI1.setMISO(ADC_MISO);
  SPI1.setMOSI(ADC_MOSI);
  SPI1.setSCK(ADC_SCLK);
  SPI1.begin();  
  SPI1.beginTransaction(SPISettings(SCLK, MSBFIRST, SPI_MODE0));

   // Configure chip select pin
  pinMode(ADC_CS, OUTPUT);
  digitalWrite(ADC_CS, HIGH);

  pinMode(LED, OUTPUT);
  digitalWrite(LED, LOW);

  pinMode(LED_RED, OUTPUT);
  digitalWrite(LED_RED, LOW);

  pinMode(LED_YELLOW, OUTPUT);
  digitalWrite(LED_YELLOW, LOW);

  pinMode(LED2, OUTPUT);
  digitalWrite(LED2, HIGH); //to show this program start

  HWSERIAL.println("setup complete");

}

void loop() {
  // put your main code here, to run repeatedly:
  if (sendSample == false && timerStart == false){
    if (usb_serial_available() == 4){
      uint8_t byte1, byte2, byte3, byte4;
      usb_serial_read(&byte1, 1);
      usb_serial_read(&byte2, 1);
      usb_serial_read(&byte3, 1);
      usb_serial_read(&byte4, 1);

      uint32_t sampleRate = (uint32_t) byte1 | (uint32_t) byte2 <<8 | (uint32_t) byte3 <<16 | (uint32_t) byte4 <<24;
      samplingRate = (float)sampleRate;
      periodMicros = 1e6/samplingRate;

      digitalWrite(LED, HIGH); //inidicate it has sampling rate 
      HWSERIAL.println("SR:");
      HWSERIAL.println(sampleRate);

      // if (samplingRate > 0 && samplingRate <= 10000){
      //   MAX_BUFFER_SIZE = 1024;
      // }
      // else if (samplingRate > 10000 && samplingRate <= 30000){
      //   MAX_BUFFER_SIZE = 2048;
      // }
      // else if (samplingRate > 30000 && samplingRate <= 50000){
      //   MAX_BUFFER_SIZE = 4096;
      // }
      // else if (samplingRate > 60000 && samplingRate <= 80000){
      //   MAX_BUFFER_SIZE = 8192;
      // }
      // else {
      //   MAX_BUFFER_SIZE = SUPER_MAX_BUFFER_SIZE;
      // }
      if (samplingRate >= 100000){
        MAX_BUFFER_SIZE = SUPER_MAX_BUFFER_SIZE;
      }
      else if (samplingRate >= 50000){
        MAX_BUFFER_SIZE = 40960;
      }
      else if (samplingRate >= 20000){
        MAX_BUFFER_SIZE = 4096;
      }
      else{
        MAX_BUFFER_SIZE = 1024;
      }
      // MAX_BUFFER_SIZE = SUPER_MAX_BUFFER_SIZE;

      HALF_MAX_BUFFER_SIZE = MAX_BUFFER_SIZE/2;

      uint8_t ACK = '1'; //notify Python it is ready
      usb_serial_write(&ACK, 1); 
      HWSERIAL.println("Send ACK");

      sendSample = false; // initally, no samples will be sent to PC.
      timerStart = true;

      nextPut = 0; //the index of the next ADC value
      nextSend = 0; // the index of the next bunch of data MCU will send to PC
      buffer_size = 0;

      totalPut = 0;
      totalSend = 0;

      timer.begin(ADC_callback, periodMicros);
    }
  }
  else if (sendSample == false && timerStart == true){
    // in this stage we need to wait until half of buffer to be full
    if(buffer_size >= HALF_MAX_BUFFER_SIZE){
      sendSample = true;
      HWSERIAL.println("sendSample = true");
    }

    // if the input wav file is very very short (smaller than half buffer)
    // we will only send that amount of data
    // THIS NEED ENTIRE HANDSHAKE TO DO TESTING
    if (usb_serial_available() > 0){
      char dummy_signal;
      usb_serial_read(&dummy_signal, usb_serial_available());
      HWSERIAL.print("dummy signal = ");
      HWSERIAL.println(dummy_signal);

      digitalWrite(LED, LOW);
      // if we receive PC's notification,
      //  we can stop ADC reading + we send what we have to PC
      timer.end();
      while (nextSend < buffer_size-512){
        usb_serial_write(byte_buffer+nextSend, 512);
        nextSend = (nextSend +512) % MAX_BUFFER_SIZE;
      }
      usb_serial_write(byte_buffer+nextSend, buffer_size-nextSend+1);
       

      sendSample = false;
      timerStart = false;

      nextPut = 0; //the index of the next ADC value
      nextSend = 0; // the index of the next bunch of data MCU will send to PC
      buffer_size = 0;

    }

  }else if(sendSample == true && timerStart == true){
    // we need to send data one by one
    if(nextSend == 0 && nextPut >= HALF_MAX_BUFFER_SIZE){
      while(nextSend != HALF_MAX_BUFFER_SIZE){
        if (usb_serial_available() > 0){
          char dummy_signal;
          usb_serial_read(&dummy_signal, usb_serial_available());
          HWSERIAL.print("dummy signal = ");
          HWSERIAL.println(dummy_signal);

          digitalWrite(LED, LOW);
          // if we receive PC's notification, we can stop ADC reading and sending
          timer.end();

          sendSample = false;
          timerStart = false;

          nextPut = 0; //the index of the next ADC value
          nextSend = 0; // the index of the next bunch of data MCU will send to PC
          buffer_size = 0;

          break;
        }
        usb_serial_write(byte_buffer+nextSend, 512);
        // HWSERIAL.println("write 512 in first half of buffer");
        nextSend += 512;
      }
      
    }else if(nextSend == HALF_MAX_BUFFER_SIZE && nextPut < HALF_MAX_BUFFER_SIZE){
      while( nextSend != 0){

        if (usb_serial_available() > 0){
          char dummy_signal;
          usb_serial_read(&dummy_signal, usb_serial_available());
          HWSERIAL.print("dummy signal = ");
          HWSERIAL.println(dummy_signal);

          digitalWrite(LED, LOW);
          // if we receive PC's notification, we can stop ADC reading and sending
          timer.end();

          sendSample = false;
          timerStart = false;

          nextPut = 0; //the index of the next ADC value
          nextSend = 0; // the index of the next bunch of data MCU will send to PC
          buffer_size = 0;

          break;
          
        }

        usb_serial_write(byte_buffer+nextSend, 512);
        // HWSERIAL.println("write 512 in second half of buffer");
        nextSend = (nextSend +512) % MAX_BUFFER_SIZE;
      }
      
    }
      
    
  }
  
}

void ADC_callback(){

  digitalWrite(ADC_CS, LOW);
  uint8_t highByte = SPI1.transfer(0x0000); //high byte
  uint8_t lowByte = SPI1.transfer(0x0000); //low byte
  // uint16_t ReadData = SPI1.transfer16(0x0000); //use this one to read data, may use transfer() to increase the speed
  digitalWrite(ADC_CS, HIGH);
  
  //transmit to python
  // Serial.println(highByte);
  // Serial.println(lowByte);
  // HWSERIAL.println(ReadData);
  //put in the array
  byte_buffer[nextPut] = lowByte;
  byte_buffer[nextPut] = highByte;
  nextPut = (nextPut +2) % MAX_BUFFER_SIZE;

  buffer_size += 2;
  // HWSERIAL.println(buffer_size);

}
