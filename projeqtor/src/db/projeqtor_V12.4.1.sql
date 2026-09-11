-- ///////////////////////////////////////////////////////////
-- // PROJECTOR                                             //
-- //-------------------------------------------------------//
-- // Version : 11.3.1                                      //
-- // Date : 2024-07-08                                     //
-- ///////////////////////////////////////////////////////////
-- Patch on V11.3

UPDATE `${prefix}menu` SET menuClass='Agile' where id in (317,318,319,320,321,328);

UPDATE `${prefix}menu` SET `idMenu`=36, `sortOrder`=4330, `level`='ReadWriteList', `menuClass`='ListOfValues ' WHERE `name`='menuScrumPriority';

