'''
Originally copied from neomanic.
Updates to the functionalities
by san-soucie (John) and Sandra,
based off of the code from 
DGonz.
'''

import serial
from serial.serialutil import SerialException

import sys
import time
import logging
import traceback

import odrive
from odrive.enums import *

import fibre

default_logger = logging.getLogger(__name__)
default_logger.setLevel(logging.DEBUG)

# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)

default_logger.addHandler(ch)

class ODriveFailure(Exception):
    pass

class ODriveInterfaceAPI(object):
    driver = None
    encoder_cpr = 4096
    right_axis = None
    left_axis = None
    connected = False
    _prerolled = False
    #engaged = False

    def __init__(self, logger=None):
        self.logger = logger if logger else default_logger

    def __del__(self):
        self.disconnect()

    def connect(self, port=None, right_axis=0, timeout=30, serial_number=None):
        print("for serious>?!")
        if self.driver:
            self.logger.info("Already connected. Disconnecting and reconnecting.")
        try:
            print("Connected, dawg")
            self.driver = odrive.find_any(timeout=timeout, logger=self.logger, serial_number=serial_number)
            self.axes = (self.driver.axis0, self.driver.axis1) 
        except:
            self.logger.error("No ODrive found. Is device powered?")
            return False

        # save some parameters for easy access
        self.right_axis = self.driver.axis0 if right_axis == 0 else self.driver.axis1
        self.left_axis  = self.driver.axis1 if right_axis == 0 else self.driver.axis0
        self.encoder_cpr = self.driver.axis0.encoder.config.cpr

        self.connected = True
        self.logger.info("Connected to ODrive. Hardware v%d.%d-%d, firmware v%d.%d.%d%s" % (
            self.driver.hw_version_major, self.driver.hw_version_minor, self.driver.hw_version_variant,
            self.driver.fw_version_major, self.driver.fw_version_minor, self.driver.fw_version_revision,
            "-dev" if self.driver.fw_version_unreleased else ""
        ))
        return True

    def disconnect(self):
        self.connected = False
        self.right_axis = None
        self.left_axis = None

        self._prerolled = False
        #self.engaged = False

        if not self.driver:
            self.logger.error("Not connected.")
            return False

        try:
            self.release()
        except:
            self.logger.error("Error in timer: " + traceback.format_exc())
            return False
        finally:
            self.driver = None
        return True

    def calibrate(self):
        if not self.driver:
            self.logger.error("Not connected.")
            return False

        self.logger.info("Vbus %.2fV" % self.driver.vbus_voltage)

        for i, axis in enumerate(self.axes):
            self.logger.info("Calibrating axis %d..." % i)
            axis.requested_state = AXIS_STATE_FULL_CALIBRATION_SEQUENCE
            time.sleep(1)
            while axis.current_state != AXIS_STATE_IDLE:
                time.sleep(0.1)
            if axis.error != 0:
                self.logger.error("Failed calibration with axis error 0x%x, motor error 0x%x" % (axis.error, axis.motor.error))
                return False

        return True

    def preroll(self, wait=True):
        if not self.driver:
            self.logger.error("Not connected.")
            return False

        if self._prerolled: # must be prerolling or already prerolled
            return False

        #self.logger.info("Vbus %.2fV" % self.driver.vbus_voltage)

        for i, axis in enumerate(self.axes):
            self.logger.info("Index search preroll axis %d..." % i)
            axis.requested_state = AXIS_STATE_ENCODER_INDEX_SEARCH

        if wait:
            for i, axis in enumerate(self.axes):
                while axis.current_state != AXIS_STATE_IDLE:
                    time.sleep(0.1)
            for i, axis in enumerate(self.axes):
                if axis.error != 0:
                    self.logger.error("Failed preroll with axis error 0x%x, motor error 0x%x" % (axis.error, axis.motor.error))
                    return False
        self._prerolled = True
        return True

    def prerolling(self):
        return self.axes[0].current_state == AXIS_STATE_ENCODER_INDEX_SEARCH or self.axes[1].current_state == AXIS_STATE_ENCODER_INDEX_SEARCH

    def prerolled(self): #
        return self._prerolled and not self.prerolling()

    def engaged(self):
        return self.axes[0].current_state == AXIS_STATE_CLOSED_LOOP_CONTROL or self.axes[1].current_state == AXIS_STATE_CLOSED_LOOP_CONTROL

    def idle(self):
        return self.axes[0].current_state == AXIS_STATE_IDLE and self.axes[1].current_state == AXIS_STATE_IDLE

    def engage(self):
        if not self.driver:
            self.logger.error("Not connected.")
            return False

        #self.logger.debug("Setting drive mode.")
        for axis in self.axes:
            axis.controller.vel_setpoint = 0
            axis.requested_state = AXIS_STATE_CLOSED_LOOP_CONTROL
            axis.controller.config.control_mode = CTRL_MODE_VELOCITY_CONTROL

        #self.engaged = True
        return True

    def release(self):
        if not self.driver:
            self.logger.error("Not connected.")
            return False
        self.logger.debug("Releasing.")
        for axis in self.axes: 
            axis.requested_state = AXIS_STATE_IDLE

        #self.engaged = False
        return True
    
    def full_init(self):
        self.driver.config.brake_resistance = 0
        for axis in self.axes:
            axis.requested_state = AXIS_STATE_IDLE
            axis.motor.config.current_lim =3 
            axis.motor.config.pole_pairs = 4
            axis.controller.config.vel_limit = 600000 #50000 counts/second is 1/8 revolution per second
            # 0.0612 [(revolutions/second)/Volt], 400000 counts per revolution
            # Max speed is 1.35 Revolutions/second, or 539000counts/second
            axis.motor.config.motor_type = MOTOR_TYPE_HIGH_CURRENT
            axis.encoder.config.cpr = 4000
            axis.encoder.config.bandwidth = 1000
            axis.encoder.config.use_index = True
            axis.encoder.config.zero_count_on_find_idx = True
            #axis.encoder.config.idx_search_speed = 1
            axis.encoder.config.pre_calibrated = False
            #motor calibration current
            axis.motor.config.calibration_current = 5
            #axis state
            if(axis.motor.config.pre_calibrated == False):
                axis.requested_state = AXIS_STATE_FULL_CALIBRATION_SEQUENCE
        print("Setup done, dawg.")
        kP_des = 2
        kD_des = 0.0003
        for axis in self.axes:
            axis.requested_state = AXIS_STATE_IDLE
            axis.motor.config.pre_calibrated = True
            axis.config.startup_encoder_index_search = True
            axis.config.startup_encoder_offset_calibration = True
            axis.controller.config.vel_gain = kD_des
            axis.controller.config.vel_integrator_gain = 0
            axis.controller.config.pos_gain = 2.0
            axis.controller.pos_setpoint = 0
            axis.controller.vel_setpoint = 0            
            axis.config.startup_closed_loop_control = True
        self.driver.save_configuration()
        print("Saved, homie")
        try:
            self.driver.reboot()
        except:
            print('Rebooted')
        time.sleep(0.25)
        # Remember to run connect() again!

    def drive(self, left_motor_val, right_motor_val):
        if not self.driver:
            self.logger.error("Not connected.")
            return
        for axis in self.axes:
            axis.requested_state = AXIS_STATE_CLOSED_LOOP_CONTROL
            axis.controller.config.control_mode = CTRL_MODE_VELOCITY_CONTROL            
        self.left_axis.controller.vel_setpoint = left_motor_val
        self.right_axis.controller.vel_setpoint = -right_motor_val

    def drivePos(self, left_motor_pos, right_motor_pos):
        if not self.driver:
            self.logger.error("Not connected.")
            return
        for axis in self.axes:
            axis.controller.config.control_mode = CTRL_MODE_POSITION_CONTROL
            axis.requested_state = AXIS_STATE_CLOSED_LOOP_CONTROL
        print(self.left_axis.controller.pos_setpoint, self.right_axis.controller.pos_setpoint)
        self.left_axis.controller.pos_setpoint = left_motor_pos
        self.right_axis.controller.pos_setpoint = right_motor_pos
        print(self.left_axis.controller.pos_setpoint, self.right_axis.controller.pos_setpoint)


    def get_errors(self, clear=True):
        # TODO: add error parsing, see: https://github.com/madcowswe/ODrive/blob/master/tools/odrive/utils.py#L34
        if not self.driver:
            return None

        axis_error = self.axes[0].error or self.axes[1].error

        if clear:
            for axis in self.axes:
                axis.error = 0
                axis.motor.error = 0
                axis.encoder.error = 0
                axis.controller.error = 0

        if axis_error:
            return "error"
