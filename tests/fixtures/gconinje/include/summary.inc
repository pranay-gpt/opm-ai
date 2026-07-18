-- This reservoir simulation deck is made available under the Open Database
-- License: http://opendatacommons.org/licenses/odbl/1.0/. Any rights in
-- individual contents of the database are licensed under the Database Contents
-- License: http://opendatacommons.org/licenses/dbcl/1.0/

-- Copyright (C) 2020 Equinor

-- This file is one of the include files for model2

-- Summary file for the base case, specific version

-- Field Data
-----------------
-- Production rates
FPR
FOPR
FWPR
FGPR
FLPR
FOPRH
FWPRH
FGPRH
FWIR
FGIR
FVPR
FVIR
-- Production cumulatives
FOPT
FWPT
FGPT
FLPT
FVPT
FVIT
-- Production ratios
FGOR
FGORH
FWCT
FWCTH

FMCTP
FMCTW
FMCTG
-- Injection rates
-- Injection cumulatives
-- Pressure and fluid
-- In-place volumes
-- Number of wells

FGLIR


-----------------
--  Region data
-----------------

RPR
 1 2 / 

ROIP
 1 2 / 

RRPV
 1 2 / 

RHPV
 1 2 / 

RWIP
 1 2 / 

ROE
 1 2 / 

ROEW
 1 2 / 

ROPT
 1 2 / 

RWPT
 1 2 / 

RWIT
 1 2 / 

-----------------
-- Well Data
-----------------
-- Production rates
WOPR
 'B-*' 'C-*' /

WGPR
 'B-*' 'C-*' /

WWPR
 'B-*' 'C-*' /

WLPR
 'B-*' 'C-*' /

WOPRH
 'B-*' 'C-*' /

WGPRH
 'B-*' 'C-*' /

WWPRH
 'B-*' 'C-*' /

WGLIR
 'B-*' 'C-*' /

WALQ
 'B-*' 'C-*' /

-- Production cumulatives
WOPT
 'B-*' 'C-*' /

WGPT
 'B-*' 'C-*' /

WWPT
 'B-*' 'C-*' /

WLPT
 'B-*' 'C-*' /


WOPTH
 'B-*' 'C-*' /

WGPTH
 'B-*' 'C-*' /

WWPTH
 'B-*' 'C-*' /

-- Production ratios

WGOR
 'B-*' 'C-*' /

WWCT
 'B-*' 'C-*' /

WGORH
 'B-*' 'C-*' /

WWCTH
 'B-*' 'C-*' /

-- Injection Rates

WGIR
 'F-*' 'G-*' /
 
WWIR
 'F-*' 'G-*' /

WGIRH
 'F-*' 'G-*' /
 
WWIRH
 'F-*' 'G-*' /

-- Pressure

WBHP
  /

WTHP
 'B-*' 'C-*' /

-- potentials 

WGIP
 'F-*' 'G-*' /

WWIP
 'F-*' 'G-*' /


WOPP
 'B-*' 'C-*' /

WGPP
 'B-*' 'C-*' /

WWPP
 'B-*' 'C-*' /



-- Group data


GOPR
  /


GWPR
  /


GGPR
  /


GLPR
  /


GGOR
  /

GMCTP
 /

GMCTW
  /


GMCTG
   /


GOPGR
  /


GGPGR
   /


GWPGR
   /


GVPGR
   /

GOPT
  /

GWPT
  /

GGPT
  /

GLPT
  /


GWIR
  /

GGIR
 /

GWIT
  /

GGIT
  /

GOPP
  /

GGPP
  /

GWPP
  /

GWPI
  /

GGPI
  /

GGLIR
  /

GVIR
 /

GVPR
  /
 
