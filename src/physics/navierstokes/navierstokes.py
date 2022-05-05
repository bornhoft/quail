# ------------------------------------------------------------------------ #
#
#       quail: A lightweight discontinuous Galerkin code for
#              teaching and prototyping
#		<https://github.com/IhmeGroup/quail>
#       
#		Copyright (C) 2020-2021
#
#       This program is distributed under the terms of the GNU
#		General Public License v3.0. You should have received a copy
#       of the GNU General Public License along with this program.  
#		If not, see <https://www.gnu.org/licenses/>.
#
# ------------------------------------------------------------------------ #

# ------------------------------------------------------------------------ #
#
#       File : src/physics/navierstokes/navierstokes.py
#
#       Contains class definitions for 1D and 2D Navier-Stokes equations.
#
# ------------------------------------------------------------------------ #
from enum import Enum
import numpy as np

import errors
import general

import physics.base.base as base
import physics.base.functions as base_fcns
from physics.base.functions import BCType as base_BC_type
from physics.base.functions import ConvNumFluxType as base_conv_num_flux_type
from physics.base.functions import DiffNumFluxType as base_diff_num_flux_type
from physics.base.functions import FcnType as base_fcn_type

import physics.euler.euler as euler
import physics.euler.functions as euler_fcns
from physics.euler.functions import BCType as euler_BC_type
from physics.euler.functions import ConvNumFluxType as \
		euler_conv_num_flux_type
from physics.euler.functions import FcnType as euler_fcn_type
from physics.euler.functions import SourceType as euler_source_type

import physics.navierstokes.functions as navierstokes_fcns
from physics.navierstokes.functions import FcnType as navierstokes_fcn_type
from physics.navierstokes.functions import SourceType as \
		navierstokes_source_type


class NavierStokes(euler.Euler):
	'''
	This class corresponds to the compressible Navier-Stokes equations. 
	It inherits attributes and methods from the Euler class. See Euler
	for detailed comments of attributes and methods. This class should 
	not be instantiated directly. Instead, the 1D and 2D variants, which
	inherit from this class (see below), should be instantiated.

	Additional methods and attributes are commented below.

	Attributes:
	-----------
	R: float
		mass-specific gas constant
	gamma: float
		specific heat ratio
	'''
	PHYSICS_TYPE = general.PhysicsType.NavierStokes

	def __init__(self):
		super().__init__()
		self.R = 0.
		self.gamma = 0.

	def set_maps(self):
		super().set_maps()

		self.diff_num_flux_map.update({
			base_diff_num_flux_type.SIP : 
				base_fcns.SIP,
			})

	def set_physical_params(self, GasConstant=287., SpecificHeatRatio=1.4, 
			PrandtlNumber=0.7, Viscosity=1.0, s=1.0, T0=1.0, beta=1.5):
		'''
		This method sets physical parameters.

		Inputs:
		-------
			GasConstant: mass-specific gas constant
			SpecificHeatRatio: ratio of specific heats
			PrandtlNumber: ratio of kinematic viscosity to thermal diffusivity
			Viscosity: fluid viscosity
			s: Sutherland model constant
			T0: Sutherland model constant
			beta: Sutherland model constant
			
		Outputs:
		--------
			self: physical parameters set
		'''
		self.R = GasConstant
		self.gamma = SpecificHeatRatio
		self.Pr = PrandtlNumber
		self.mu0 = Viscosity
		self.s = s
		self.T0 = T0
		self.beta = beta


class NavierStokes1D(NavierStokes, euler.Euler1D):
	'''
	This class corresponds to 1D Navier Stokes equations.
	It inherits attributes and methods from the NavierStokes class.
	See NavierStokes for detailed comments of attributes and methods.

	Additional methods and attributes are commented below.
	'''
	NUM_STATE_VARS = 3
	NDIMS = 1

	def set_maps(self):
		super().set_maps()

	def get_diff_flux_interior(self, Uq, gUq):
		# Get indices/slices of state variables
		irho, irhou, irhoE = self.get_state_indices()
		smom = self.get_momentum_slice()

		# Unpack state coefficients
		rho  = Uq[:, :, irho]  # [n, nq]
		rhou = Uq[:, :, irhou] # [n, nq]
		rhoE = Uq[:, :, irhoE] # [n, nq]
		mom  = Uq[:, :, smom]  # [n, nq, ndims]

		# Calculate transport
		mu, kappa = self.get_transport(self, Uq, 
			flag_non_physical=False)
		mu = mu.reshape(rho.shape)
		kappa = kappa.reshape(rho.shape)
		nu = mu / rho

		gamma = self.gamma
		R = self.R

		# Set constants for stress tensor
		C1 = 2. / 3.
		C2 = (gamma - 1.) / (R * rho)
		
		# Separate x gradient
		gUx = gUq[:, :, :, 0] # [ne, nq, ns]

		# Get velocity
		u = rhou / rho
		
		# Get E
		E = rhoE / rho
		
		# Get squared velocity
		u2 = u**2

		# Store dTdU
		dTdU = np.zeros_like(gUx)
		dTdU[:, :, 0] = C2 * (-E + u2)
		dTdU[:, :, 1] = C2 * -u
		dTdU[:, :, 2] = C2

		# Get the stress tensor (use product rules to write in 
		# terms of the conservative gradients)
		rhodiv = (gUx[:, :, 1] - u * gUx[:, :, 0])
		tauxx = nu * (2. * (gUx[:, :, 1] - u * gUx[:, :, 0]) - \
			C1 * rhodiv)

		# Assemble flux matrix
		F = np.empty(Uq.shape + (self.NDIMS,)) # [n, nq, ns, ndims]
		F[:,:,irho,  :] = 0.		   # flux of rho 
		F[:,:,irhou, 0] = tauxx 	# flux of momentum
		F[:,:,irhoE, 0] = u * tauxx + \
			kappa * np.einsum('ijk, ijk -> ij', dTdU, gUx)

		return F # [n, nq, ns, ndims]

class NavierStokes2D(NavierStokes, euler.Euler2D):
	'''
	This class corresponds to 2D Navier-Stokes equations. It 
	inherits attributes and methods from the Navier-Stokes class as 
	well as the Euler2D class.
	See Navier-Stokes and Euler2D for detailed comments of 
	attributes and methods.

	Additional methods and attributes are commented below.
	'''
	NUM_STATE_VARS = 4
	NDIMS = 2

	def __init__(self):
		super().__init__()

	def set_maps(self):
		super().set_maps()

		d = {
			navierstokes_fcn_type.TaylorGreenVortexNS : 
					navierstokes_fcns.TaylorGreenVortexNS,
			navierstokes_fcn_type.ManufacturedSolution : 
					navierstokes_fcns.ManufacturedSolution,
		}

		self.IC_fcn_map.update(d)
		self.exact_fcn_map.update(d)
		self.BC_fcn_map.update(d)

		self.source_map.update({
			navierstokes_source_type.ManufacturedSource : 
					navierstokes_fcns.ManufacturedSource,
		})

	def get_diff_flux_interior(self, Uq, gUq):
		# Get indices/slices of state variables
		irho, irhou, irhov, irhoE = self.get_state_indices()
		smom = self.get_momentum_slice()

		# Unpack state coefficients
		rho  = Uq[:, :, irho]  # [n, nq]
		rhou = Uq[:, :, irhou] # [n, nq]
		rhov = Uq[:, :, irhov] # [n, nq]
		rhoE = Uq[:, :, irhoE] # [n, nq]
		mom  = Uq[:, :, smom]  # [n, nq, ndims]

		# Calculate transport
		mu, kappa = self.get_transport(self, Uq, 
			flag_non_physical=False)
		mu = mu.reshape(rho.shape)
		kappa = kappa.reshape(rho.shape)
		nu = mu / rho

		gamma = self.gamma
		R = self.R

		# Set constants for stress tensor
		C1 = 2. / 3.
		C2 = (gamma - 1.) / (R * rho)
		
		# Separate x and y gradients
		gUx = gUq[:, :, :, 0] # [ne, nq, ns]
		gUy = gUq[:, :, :, 1] # [ne, nq, ns]

		# Get velocity in each dimension
		u = rhou / rho
		v = rhov / rho
		
		# Get E
		E = rhoE / rho
		
		# Get squared velocities
		u2 = u**2
		v2 = v**2

		# Store dTdU
		dTdU = np.zeros_like(gUx)
		dTdU[:, :, 0] = C2 * (-E + u2 + v2)
		dTdU[:, :, 1] = C2 * -u
		dTdU[:, :, 2] = C2 * -v
		dTdU[:, :, 3] = C2

		# Get the stress tensor (use product rules to write in 
		# terms of the conservative gradients)
		rhodiv = ((gUx[:, :, 1] - u * gUx[:, :, 0]) + \
			(gUy[:, :, 2] - v * gUy[:, :, 0]))
		tauxx = nu * (2. * (gUx[:, :, 1] - u * gUx[:, :, 0]) - \
			C1 * rhodiv)
		tauxy = nu * ((gUy[:, :, 1] - u * gUy[:, :, 0]) + \
			(gUx[:, :, 2] - v * gUx[:, :, 0]))
		tauyy = nu * (2. * (gUy[:, :, 2] - v * gUy[:, :, 0]) - \
			C1 * rhodiv)

		# Assemble flux matrix
		F = np.empty(Uq.shape + (self.NDIMS,)) # [n, nq, ns, ndims]
		F[:,:,irho,  :] = 0.		   # x,y-flux of rho (zero both dir)

		# x-direction
		F[:,:,irhou, 0] = tauxx 	# x-flux of x-momentum
		F[:,:,irhov, 0] = tauxy     # x-flux of y-momentum
		F[:,:,irhoE, 0] = u * tauxx + v * tauxy + \
			kappa * np.einsum('ijk, ijk -> ij', dTdU, gUx)

		# y-direction
		F[:,:,irhou, 1] = tauxy        # y-flux of x-momentum
		F[:,:,irhov, 1] = tauyy 	   # y-flux of y-momentum
		F[:,:,irhoE, 1] = u * tauxy + v * tauyy + \
			kappa * np.einsum('ijk, ijk -> ij', dTdU, gUy)

		return F # [n, nq, ns, ndims]
		
		
		
class Twophase(NavierStokes2D, euler.Euler2D):
	'''
	This class corresponds to 2D Two-phase Navier-Stokes equations. It
	inherits attributes and methods from the Navier-Stokes2D class as
	well as the Euler2D class.

	Additional methods and attributes are commented below.
	'''
	NUM_STATE_VARS = 7
	NDIMS = 2
	PHYSICS_TYPE = general.PhysicsType.Twophase

	def __init__(self):
		super().__init__()
		self.gamma1 = 0.
		self.gamma2 = 0.
		self.pinf1 = 0.
		self.pinf2 = 0.
		self.mu1 = 0.
		self.mu2 = 0.
		self.kappa1 = 0.
		self.kappa2 = 0.
		self.rho01 = 0.
		self.rho02 = 0.
		
		self.eps = 0.
		self.switch = 0.
		
	def set_maps(self):
		super().set_maps()

		d = {
			navierstokes_fcn_type.Bubble :
					navierstokes_fcns.Bubble
		}

		self.IC_fcn_map.update(d)
		self.exact_fcn_map.update(d)
		self.BC_fcn_map.update(d)

		self.source_map.update({
			navierstokes_source_type.BubbleSource :
					navierstokes_fcns.BubbleSource,
		})
		
	def set_physical_params(self, gamma1=1., gamma2=1., mu1=1., mu2=1., \
			kappa1=1., kappa2=1., pinf1=1., pinf2=1., rho01=1., rho02=1., eps=0.):
		'''
		This method sets physical parameters.

		Inputs:
		-------
		Outputs:
		--------
		'''
		self.gamma1 = gamma1
		self.gamma2 = gamma2
		self.pinf1 = pinf1
		self.pinf2 = pinf2
		self.mu1 = mu1
		self.mu2 = mu2
		self.kappa1 = kappa1
		self.kappa2 = kappa2
		self.rho01 = rho01
		self.rho02 = rho02
		self.eps = eps

	class StateVariables(Enum):
		Density1 = "\\rho1 \\phi1"
		Density2 = "\\rho2 \\phi2"
		XMomentum = "\\rho u"
		YMomentum = "\\rho v"
		Energy = "\\rho E"
		PhaseField = "\\phi"
		LevelSet = "\\psi"
		
	class AdditionalVariables(Enum):
		Pressure = "p"
		XVelocity = "v_x"
		YVelocity = "v_y"
		Density = "\\rho"
		
		
	def get_state_indices(self):
		irho1phi1 = self.get_state_index("Density1")
		irho2phi2 = self.get_state_index("Density2")
		irhou = self.get_state_index("XMomentum")
		irhov = self.get_state_index("YMomentum")
		irhoE = self.get_state_index("Energy")
		iPF = self.get_state_index("PhaseField")
		iLS = self.get_state_index("LevelSet")

		return irho1phi1, irho2phi2, irhou, irhov, irhoE, iPF, iLS


	def get_conv_flux_interior(self, Uq, gUq, x=None, t=None):
		# Get indices/slices of state variables
		irho1phi1, irho2phi2, irhou, irhov, irhoE, iPF, iLS = self.get_state_indices()

		rho1phi1  = Uq[:, :, irho1phi1] # [n, nq]
		rho2phi2  = Uq[:, :, irho2phi2] # [n, nq]
		rhou      = Uq[:, :, irhou]     # [n, nq]
		rhov      = Uq[:, :, irhov]     # [n, nq]
		rhoE      = Uq[:, :, irhoE]     # [n, nq]
		phi1      = Uq[:, :, iPF]       # [n, nq]
		LS        = Uq[:, :, iLS]       # [n, nq]
		
		gLS = gUq[:,:,iLS,:]
		n = np.zeros(gLS.shape)
		mag = np.sqrt(gLS[:,:,0]**2+gLS[:,:,1]**2)
		n[:,:,0] = gLS[:,:,0]/mag
		n[:,:,1] = gLS[:,:,1]/mag

		# Get velocity in each dimension
		rho  = rho1phi1 + rho2phi2
		u = rhou / rho
		v = rhov / rho
		# Get squared velocities
		u2 = u**2
		v2 = v**2
		mag = np.sqrt(u2+v2)
		gam = np.max(mag)
		k = 0.5*(u2 + v2)
		
		# Calculate transport
		gamma1=self.gamma1
		gamma2=self.gamma2
		pinf1=self.pinf1
		pinf2=self.pinf2
		rho01=self.rho01
		rho02=self.rho02

		# Calculate pressure using the Ideal Gas Law
#		p = (self.gamma - 1.)*(rhoE - rho * k) # [n, nq]

		# Stiffened gas EOS
		# Get properties of the fluid: gamma_l, pinf_l
		rhoe = (rhoE - 0.5 * rho * (u2 + v2)) # [n, nq]
		one_over_gamma = phi1/(gamma1-1.0) + (1.0-phi1)/(gamma2-1.0)
		gamma = (one_over_gamma+1.0)/one_over_gamma
		pinf = (gamma-1.0)/gamma*(phi1*gamma1*pinf1/(gamma1-1.0) + (1.0-phi1)*gamma2*pinf2/(gamma2-1.0))
		p = rhoe/one_over_gamma - gamma*pinf

		# Get off-diagonal momentum
		rhouv = rho * u * v
		# Get total enthalpy
		H = rhoE + p

		# Correction terms
		a1x = -phi1*(1.0-phi1)*n[:,:,0]
		a1y = -phi1*(1.0-phi1)*n[:,:,1]
		a2x = -a1x
		a2y = -a1y

		fx = (rho01-rho02)*a1x
		fy = (rho01-rho02)*a1y
		
		rho1 = rho1phi1/phi1
		rho2 = rho2phi2/(1.0-phi1)
		h1 = (p + pinf1)*gamma1/(rho1*(gamma1-1.0))
		h2 = (p + pinf2)*gamma2/(rho2*(gamma2-1.0))

		# Assemble flux matrix (missing a correction term in energy equation)
		F = np.empty(Uq.shape + (self.NDIMS,)) # [n, nq, ns, ndims]
		F[:,:,irho1phi1,  0] = u * rho1phi1 - rho01*a1x # x-mass1 flux
		F[:,:,irho1phi1,  1] = v * rho1phi1 - rho01*a1y # y-mass1 flux
		F[:,:,irho2phi2,  0] = u * rho2phi2 - rho02*a2x # x-mass2 flux
		F[:,:,irho2phi2,  1] = v * rho2phi2 - rho02*a2y # y-mass2 flux
		F[:,:,irhou, 0] = rho * u2 + p - fx * u   # x-flux of x-momentum
		F[:,:,irhov, 0] = rhouv        - fx * v   # x-flux of y-momentum
		F[:,:,irhou, 1] = rhouv        - fy * u   # y-flux of x-momentum
		F[:,:,irhov, 1] = rho * v2 + p - fy * v   # y-flux of y-momentum
		F[:,:,irhoE, 0] = H * u        - fx * k - (rho1*h1-rho2*h2)*a1x # x-flux of energy
		F[:,:,irhoE, 1] = H * v        - fy * k - (rho1*h1-rho2*h2)*a1y # y-flux of energy
		F[:,:,iPF,  0]  = u * phi1 - a1x  # x-flux of phi1
		F[:,:,iPF,  1]  = v * phi1 - a1y  # y-flux of phi1
		F[:,:,iLS,  0]  = u * LS          # x-flux of Levelset
		F[:,:,iLS,  1]  = v * LS          # y-flux of Levelset

		return F, (u2, v2, rho, p)


	def get_diff_flux_interior(self, Uq, gUq, x, t, epsilon):
		# Get indices/slices of state variables
		irho1phi1, irho2phi2, irhou, irhov, irhoE, iPF, iLS = self.get_state_indices()

		rho1phi1  = Uq[:, :, irho1phi1] # [n, nq]
		rho2phi2  = Uq[:, :, irho2phi2] # [n, nq]
		rhou      = Uq[:, :, irhou]     # [n, nq]
		rhov      = Uq[:, :, irhov]     # [n, nq]
		rhoE      = Uq[:, :, irhoE]     # [n, nq]
		phi1      = Uq[:, :, iPF]       # [n, nq]
		LS        = Uq[:, :, iLS]       # [n, nq]

		# Calculate transport
		mu1=self.mu1
		mu2=self.mu2
		kappa1=self.kappa1
		kappa2=self.kappa2
		gamma1=self.gamma1
		gamma2=self.gamma2
		pinf1=self.pinf1
		pinf2=self.pinf2
		rho01=self.rho01
		rho02=self.rho02
			
		mu    = mu1*phi1 + mu2*(1.0-phi1)
		kappa = kappa1*phi1 + kappa2*(1.0-phi1)
		rho   = rho1phi1 + rho2phi2
		one_over_gamma = phi1/(gamma1-1.0) + (1.0-phi1)/(gamma2-1.0)
		gamma = (one_over_gamma+1.0)/one_over_gamma

		# Separate x and y gradients
		gUx = gUq[:, :, :, 0] # [ne, nq, ns]
		gUy = gUq[:, :, :, 1] # [ne, nq, ns]

		# Get velocity in each dimension
		u = rhou / rho
		v = rhov / rho
		
		# Get E
		E = rhoE / rho
		
		# Get squared velocities
		u2 = u**2
		v2 = v**2
		mag = np.sqrt(u2+v2)
		gam = np.max(mag)
		k = 0.5*(u2 + v2)

		# Get the stress tensor (use product rules to write in
		# terms of the conservative gradients)
		dudx = gUx[:,:,2] - u * (gUx[:,:,0] + gUx[:,:,1])
		dudy = gUy[:,:,2] - u * (gUy[:,:,0] + gUy[:,:,1])
		dvdx = gUx[:,:,3] - v * (gUx[:,:,0] + gUx[:,:,1])
		dvdy = gUy[:,:,3] - v * (gUy[:,:,0] + gUy[:,:,1])
		
		tauxx = 2.0*mu*(dudx - 1.0/2.0*(dudx + dvdx))
		tauxy = 1.0*mu*(dudy + dvdx)
		tauyy = 2.0*mu*(dvdy - 1.0/2.0*(dudx + dvdx))
		
		# Correction terms
		eps = self.eps
		a1x = gam*eps*gUx[:,:,5]
		a1y = gam*eps*gUy[:,:,5]
		a2x = -a1x
		a2y = -a1y
		
		fx = rho01*a1x + rho02*a2x
		fy = rho01*a1y + rho02*a2y
		
		# Stiffened gas EOS
		rhoe = (rhoE - 0.5 * rho * (u2 + v2)) # [n, nq]
		one_over_gamma = phi1/(gamma1-1.0) + (1.0-phi1)/(gamma2-1.0)
		gamma = (one_over_gamma+1.0)/one_over_gamma
		pinf = (gamma-1.0)/gamma*(phi1*gamma1*pinf1/(gamma1-1.0) + (1.0-phi1)*gamma2*pinf2/(gamma2-1.0))
		p = rhoe/one_over_gamma - gamma*pinf
		
		rho1 = rho1phi1/phi1
		rho2 = rho2phi2/(1.0-phi1)
		h1 = (p + pinf1)*gamma1/(rho1*(gamma1-1))
		h2 = (p + pinf2)*gamma2/(rho2*(gamma2-1))

		# Assemble flux matrix
		F = np.empty(Uq.shape + (self.NDIMS,)) # [n, nq, ns, ndims]
		F[:,:,irho1phi1,  0] = rho01*a1x # x-mass1 flux
		F[:,:,irho1phi1,  1] = rho01*a1y # y-mass1 flux
		F[:,:,irho2phi2,  0] = rho02*a2x # x-mass2 flux
		F[:,:,irho2phi2,  1] = rho02*a2y # y-mass2 flux

		# x-direction
		F[:,:,irhou, 0] = tauxx + fx * u # x-flux of x-momentum
		F[:,:,irhov, 0] = tauxy + fx * v # x-flux of y-momentum
		F[:,:,irhoE, 0] = u * tauxx + v * tauxy  \
			+ fx * k + (rho1*h1-rho2*h2)*a1x

		# y-direction
		F[:,:,irhou, 1] = tauxy + fy * u # y-flux of x-momentum
		F[:,:,irhov, 1] = tauyy + fy * v # y-flux of y-momentum
		F[:,:,irhoE, 1] = u * tauxy + v * tauyy + \
			+ fy * k + (rho1*h1-rho2*h2)*a1y
			
		# phase field and level set
		F[:,:,iPF,  0]  = a1x # x-flux of phi1
		F[:,:,iPF,  1]  = a1y # y-flux of phi1
		F[:,:,iLS,  0]  = 0.0       # x-flux of Levelset
		F[:,:,iLS,  1]  = 0.0       # y-flux of Levelset

		return F # [n, nq, ns, ndims]

	def compute_additional_variable(self, var_name, Uq, gUq, flag_non_physical, x, t):
		sname = self.AdditionalVariables[var_name].name
		# Get indices/slices of state variables
		irho1phi1, irho2phi2, irhou, irhov, irhoE, iPF, iLS = self.get_state_indices()

		rho1phi1  = Uq[:, :, irho1phi1] # [n, nq]
		rho2phi2  = Uq[:, :, irho2phi2] # [n, nq]
		rhou      = Uq[:, :, irhou]     # [n, nq]
		rhov      = Uq[:, :, irhov]     # [n, nq]
		rhoE      = Uq[:, :, irhoE]     # [n, nq]
		phi1      = Uq[:, :, iPF]       # [n, nq]
		LS        = Uq[:, :, iLS]       # [n, nq]
		

		if sname is self.AdditionalVariables["Pressure"].name:
			# Calculate transport
			gamma1=self.gamma1
			gamma2=self.gamma2
			pinf1=self.pinf1
			pinf2=self.pinf2

			rho   = rho1phi1 + rho2phi2
			one_over_gamma = phi1/(gamma1-1.0) + (1.0-phi1)/(gamma2-1.0)
			gamma = (one_over_gamma+1.0)/one_over_gamma
			# Get velocity in each dimension
			u = rhou / rho
			v = rhov / rho
			u2 = u**2
			v2 = v**2
			rhoe = (rhoE - 0.5 * rho * (u2 + v2)) # [n, nq]
			one_over_gamma = phi1/(gamma1-1.0) + (1.0-phi1)/(gamma2-1.0)
			gamma = (one_over_gamma+1.0)/one_over_gamma
			pinf = (gamma-1.0)/gamma*(phi1*gamma1*pinf1/(gamma1-1.0) + (1.0-phi1)*gamma2*pinf2/(gamma2-1.0))
			p = rhoe/one_over_gamma - gamma*pinf
			scalar = p
		elif sname is self.AdditionalVariables["XVelocity"].name:
			rho   = rho1phi1 + rho2phi2
			# Get velocity in each dimension
			scalar = rhou / rho
		elif sname is self.AdditionalVariables["YVelocity"].name:
			rho   = rho1phi1 + rho2phi2
			# Get velocity in each dimension
			scalar = rhov / rho
		elif sname is self.AdditionalVariables["Density"].name:
			rho   = rho1phi1 + rho2phi2
			# Get velocity in each dimension
			scalar = rho
		else:
			raise NotImplementedError

		return scalar
