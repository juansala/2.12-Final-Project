import numpy as np
import cv2
import glob

# termination criteria
criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

# checkerboard Dimensions
cbrow = 6
cbcol = 9

# prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
objp = np.zeros((cbrow * cbcol, 3), np.float32)
objp[:, :2] = np.mgrid[0:cbcol, 0:cbrow].T.reshape(-1, 2)

# Arrays to store object points and image points from all the images.
objpoints = [] # 3d point in real world space
imgpoints = [] # 2d points in image plane.

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_AUTOFOCUS, 0) # turn the autofocus off

for i in range(0, 40):
	ret, frame = cap.read()
	frame = frame[0:440,100:560]
	gray = cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)

	# Find the chess board corners
	ret, corners = cv2.findChessboardCorners(gray, (cbcol, cbrow), None)

	# If found, add object points, image points (after refining them)
	if ret == True:
	    objpoints.append(objp)

	    corners2 = cv2.cornerSubPix(gray,corners,(11,11),(-1,-1),criteria)
	    imgpoints.append(corners2)

	    # Draw and display the corners
	    frame = cv2.drawChessboardCorners(frame, (7,6), corners2,ret)
	    cv2.imshow('img',frame)
	    cv2.waitKey(400)

cap.release()
cv2.destroyAllWindows()

ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)
print(mtx)
print(dist)
print(rvecs)
print(tvecs)
