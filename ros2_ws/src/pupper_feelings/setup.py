from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'pupper_feelings'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/resources', glob('resources/*')),
        ('share/' + package_name + '/launch', glob('launch/*.py')),
    ],
    install_requires=[
        'setuptools',
        ],
    zip_safe=True,
    maintainer='pi',
    maintainer_email='nathankau@gmail.com',
    description='TODO Package description',
    license='TODO: License declaration',
    entry_points={
        'console_scripts': [
            'ear_control = pupper_feelings.ear_control:main',
            'face_control = pupper_feelings.face_control:main',
            'face_control_gui = pupper_feelings.face_control_gui:main',
            'robot_hop = pupper_feelings.robot_hop:main',
        ],
    }
)
