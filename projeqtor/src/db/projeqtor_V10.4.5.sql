-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 10.4.5                                      //
-- // Date : 2023-08-17                                     //
-- ///////////////////////////////////////////////////////////
-- Patch on V10.4

DELETE FROM `${prefix}parameter` WHERE parameterCode='timeZone' and parameterValue='Africa/Abidjan' and idUser is not null;