from setuptools import find_packages, setup

package_name = 'tb3_controller'

setup(
    name=package_name,
    version='1.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Your Name',
    maintainer_email='you@email.com',
    description='TurtleBot3 controller',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'move_to_pose_node = tb3_controller.move_to_pose_node:main',
        ],
    },
)
